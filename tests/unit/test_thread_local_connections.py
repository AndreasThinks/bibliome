"""Tests for thread-local database connections and cursor safety."""

import pytest
import threading
import time
import sqlite3
import tempfile
import os
from unittest.mock import patch, MagicMock
import random


@pytest.fixture(autouse=True)
def reset_connection_pool():
    """Reset the global connection pool state before and after each test."""
    from models import get_connection_pool, _thread_local
    
    # Reset pool state before test
    pool = get_connection_pool()
    original_main_db = pool._main_db
    pool._main_db = None
    
    # Clear thread-local connection
    if hasattr(_thread_local, 'connection'):
        try:
            if _thread_local.connection:
                _thread_local.connection.close()
        except:
            pass
        _thread_local.connection = None
    
    yield
    
    # Restore/cleanup after test
    pool._main_db = original_main_db
    if hasattr(_thread_local, 'connection'):
        try:
            if _thread_local.connection:
                _thread_local.connection.close()
        except:
            pass
        _thread_local.connection = None


class TestThreadLocalConnectionPool:
    """Tests for the ThreadLocalConnectionPool class."""
    
    def test_pool_creates_connections_per_thread(self):
        """Verify each thread gets its own isolated connection."""
        from models import ThreadLocalConnectionPool, _thread_local
        
        # Create temp database with WAL mode pre-configured
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Pre-create the database with WAL mode to avoid PRAGMA race conditions
            setup_conn = sqlite3.connect(db_path)
            setup_conn.execute("PRAGMA journal_mode=WAL")
            setup_conn.execute("CREATE TABLE dummy (id INTEGER)")
            setup_conn.commit()
            setup_conn.close()
            
            pool = ThreadLocalConnectionPool(db_path)
            pool._main_db = MagicMock()  # Simulate initialized pool
            
            connections = []
            errors = []
            lock = threading.Lock()
            
            def get_connection_info():
                try:
                    conn = pool.get_connection()
                    with lock:
                        connections.append(id(conn))
                except Exception as e:
                    with lock:
                        errors.append(str(e))
            
            threads = []
            for i in range(5):
                t = threading.Thread(target=get_connection_info, name=f"TestThread-{i}")
                threads.append(t)
                # Stagger thread starts slightly to avoid PRAGMA race
                t.start()
                time.sleep(0.01)
            
            for t in threads:
                t.join()
            
            # Check that threads completed without errors
            assert len(errors) == 0, f"Thread errors: {errors}"
            # Each thread should have gotten a unique connection
            assert len(set(connections)) == 5, f"Each thread should get its own connection, got {len(set(connections))}"
            
        finally:
            # Cleanup
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    def test_same_thread_reuses_connection(self):
        """Verify the same thread reuses its existing connection."""
        from models import ThreadLocalConnectionPool, _thread_local
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            pool = ThreadLocalConnectionPool(db_path)
            pool._main_db = MagicMock()
            
            # Get connection twice from same thread
            conn1 = pool.get_connection()
            conn2 = pool.get_connection()
            
            assert id(conn1) == id(conn2), "Same thread should reuse connection"
            
        finally:
            pool.close_connection()
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    def test_close_connection(self):
        """Verify close_connection properly cleans up."""
        from models import ThreadLocalConnectionPool, _thread_local
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            pool = ThreadLocalConnectionPool(db_path)
            pool._main_db = MagicMock()
            
            # Get a connection
            conn1 = pool.get_connection()
            assert conn1 is not None
            
            # Close it
            pool.close_connection()
            
            # Getting connection again should create a new one
            conn2 = pool.get_connection()
            assert id(conn1) != id(conn2), "Should create new connection after close"
            
        finally:
            pool.close_connection()
            if os.path.exists(db_path):
                os.unlink(db_path)


class TestSafeExecuteQuery:
    """Tests for the safe_execute_query function."""
    
    def test_basic_query_execution(self):
        """Test basic query execution returns correct results."""
        from models import safe_execute_query, get_connection_pool
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Create a test database with data
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
            conn.execute("INSERT INTO test (name) VALUES (?)", ("test1",))
            conn.execute("INSERT INTO test (name) VALUES (?)", ("test2",))
            conn.commit()
            
            # Test safe_execute_query
            results = safe_execute_query(conn, "SELECT * FROM test ORDER BY id")
            
            assert len(results) == 2
            assert results[0]['name'] == "test1"
            assert results[1]['name'] == "test2"
            
        finally:
            conn.close()
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    def test_returns_empty_for_no_results(self):
        """Test returns empty list when no results."""
        from models import safe_execute_query
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
            conn.commit()
            
            results = safe_execute_query(conn, "SELECT * FROM test WHERE id = ?", (999,))
            
            assert results == []
            
        finally:
            conn.close()
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    def test_retry_on_cursor_error(self):
        """Test that cursor errors trigger retry with backoff."""
        from models import safe_execute_query
        import logging
        
        # Mock a database that fails twice then succeeds
        mock_db = MagicMock()
        call_count = [0]
        
        def mock_execute(query, params):
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("Can't get description for statements that have completed execution")
            
            # Return a mock cursor on third call
            mock_cursor = MagicMock()
            mock_cursor.description = [('id',), ('name',)]
            mock_cursor.fetchall.return_value = [(1, 'test')]
            return mock_cursor
        
        mock_db.execute = mock_execute
        
        # This should succeed after retries
        results = safe_execute_query(mock_db, "SELECT * FROM test", ())
        
        assert call_count[0] == 3, "Should have retried twice before succeeding"
        assert len(results) == 1
        assert results[0]['id'] == 1
    
    def test_returns_empty_after_max_retries(self):
        """Test returns empty list after exhausting retries."""
        from models import safe_execute_query
        
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("Can't get description for statements that have completed execution")
        
        results = safe_execute_query(mock_db, "SELECT * FROM test", (), max_retries=3)
        
        assert results == []
        assert mock_db.execute.call_count == 3
    
    def test_database_busy_retry(self):
        """Test retry behavior on database busy errors."""
        from models import safe_execute_query
        
        mock_db = MagicMock()
        call_count = [0]
        
        def mock_execute(query, params):
            call_count[0] += 1
            if call_count[0] < 2:
                raise sqlite3.OperationalError("database is locked")
            
            mock_cursor = MagicMock()
            mock_cursor.description = [('id',)]
            mock_cursor.fetchall.return_value = [(1,)]
            return mock_cursor
        
        mock_db.execute = mock_execute
        
        results = safe_execute_query(mock_db, "SELECT * FROM test", ())
        
        assert call_count[0] == 2
        assert len(results) == 1


class TestConcurrentAccess:
    """Tests for concurrent database access scenarios."""
    
    def test_concurrent_reads_isolated(self):
        """Test that concurrent reads from multiple threads work correctly."""
        from models import safe_execute_query, get_connection_pool, ThreadLocalConnectionPool
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Setup database with WAL mode for better concurrent access
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT)")
            for i in range(100):
                conn.execute("INSERT INTO books (title) VALUES (?)", (f"Book {i}",))
            conn.commit()
            conn.close()
            
            # Create connection pool
            pool = ThreadLocalConnectionPool(db_path)
            pool._main_db = MagicMock()
            
            results = []
            errors = []
            
            def read_books():
                try:
                    thread_conn = pool.get_connection()
                    # Perform multiple reads
                    for _ in range(10):
                        data = safe_execute_query(thread_conn, "SELECT * FROM books ORDER BY id LIMIT 10", ())
                        results.append(len(data))
                        time.sleep(random.uniform(0.001, 0.01))  # Random delay
                except Exception as e:
                    errors.append(str(e))
            
            # Start multiple threads
            threads = []
            for i in range(10):
                t = threading.Thread(target=read_books)
                threads.append(t)
                t.start()
            
            for t in threads:
                t.join()
            
            # All reads should succeed
            assert len(errors) == 0, f"Errors occurred: {errors}"
            assert len(results) == 100  # 10 threads * 10 reads each
            assert all(r == 10 for r in results), "All reads should return 10 results"
            
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    def test_concurrent_reads_and_writes(self):
        """Test concurrent read and write operations don't cause cursor errors."""
        from models import get_connection_pool, ThreadLocalConnectionPool
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Setup database with WAL mode
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("CREATE TABLE counters (id INTEGER PRIMARY KEY, value INTEGER)")
            conn.execute("INSERT INTO counters (value) VALUES (0)")
            conn.commit()
            conn.close()
            
            pool = ThreadLocalConnectionPool(db_path)
            pool._main_db = MagicMock()
            
            read_results = []
            write_results = []
            errors = []
            
            def reader():
                try:
                    thread_conn = pool.get_connection()
                    for _ in range(20):
                        cursor = thread_conn.execute("SELECT value FROM counters WHERE id = 1")
                        result = cursor.fetchone()
                        if result:
                            read_results.append(result[0])
                        time.sleep(random.uniform(0.001, 0.005))
                except Exception as e:
                    errors.append(f"Read error: {e}")
            
            def writer():
                try:
                    thread_conn = pool.get_connection()
                    for i in range(10):
                        thread_conn.execute("UPDATE counters SET value = value + 1 WHERE id = 1")
                        thread_conn.commit()
                        write_results.append(i)
                        time.sleep(random.uniform(0.001, 0.005))
                except Exception as e:
                    errors.append(f"Write error: {e}")
            
            # Start readers and writers
            threads = []
            for i in range(5):
                threads.append(threading.Thread(target=reader, name=f"Reader-{i}"))
            for i in range(2):
                threads.append(threading.Thread(target=writer, name=f"Writer-{i}"))
            
            for t in threads:
                t.start()
            
            for t in threads:
                t.join()
            
            # Should complete without cursor errors
            assert len(errors) == 0, f"Errors occurred: {errors}"
            assert len(write_results) == 20, "All writes should complete"
            assert len(read_results) > 0, "Reads should have completed"
            
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


class TestExponentialBackoffWithJitter:
    """Tests for the exponential backoff and jitter implementation."""
    
    def test_backoff_delays_increase(self):
        """Verify that retry delays increase with each attempt."""
        from models import safe_execute_query
        import time
        
        mock_db = MagicMock()
        
        start_times = []
        
        def mock_execute(query, params):
            start_times.append(time.time())
            raise Exception("Can't get description for statements that have completed execution")
        
        mock_db.execute = mock_execute
        
        safe_execute_query(mock_db, "SELECT 1", (), max_retries=4)
        
        # Check that delays between attempts increase
        delays = []
        for i in range(1, len(start_times)):
            delays.append(start_times[i] - start_times[i-1])
        
        # Each delay should be generally larger than the previous
        # (allowing for some jitter variation)
        assert len(delays) == 3, "Should have 3 delays between 4 attempts"
        # The later delays should be noticeably longer on average
        assert delays[2] > delays[0] * 1.5, "Later delays should be significantly longer"


class TestConnectionPoolInitialization:
    """Tests for connection pool initialization in setup_database."""
    
    def test_pool_initialized_on_setup(self):
        """Verify connection pool is initialized when setup_database is called."""
        from models import setup_database, get_connection_pool
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, 'test.db')
            
            # Setup database
            db_tables = setup_database(db_path=db_path, memory=True)
            
            # Pool should be initialized
            pool = get_connection_pool()
            assert pool._main_db is not None, "Connection pool should have main_db set"
