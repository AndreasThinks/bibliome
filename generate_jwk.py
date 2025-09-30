#!/usr/bin/env python3
"""
Generate ES256 JWK for atproto OAuth client.
Run this script to generate a new client secret keypair.
"""
import json
import sys
import os
from authlib.jose import JsonWebKey

def generate_client_jwk():
    """Generate ES256 keypair for OAuth client."""
    print("🔐 Generating ES256 keypair for atproto OAuth client...")

    try:
        # Generate ES256 keypair
        private_key = JsonWebKey.generate_key("EC", "P-256", is_private=True)

        # Export private key as JSON
        private_jwk = json.loads(private_key.as_json(is_private=True))

        # Export public key as JSON
        public_jwk = json.loads(private_key.as_json(is_private=False))

        print("✅ Keypair generated successfully!")
        print()
        print("📋 Private Key (add to .env):")
        print(f'CLIENT_SECRET_JWK={json.dumps(private_jwk, separators=(",", ":"))}')
        print()
        print("📋 Public Key (for reference):")
        print(json.dumps(public_jwk, indent=2))
        print()

        # Validate the key
        print("🔍 Validating keypair...")
        test_message = b"Hello, atproto OAuth!"

        # Sign with private key
        from authlib.jose import jwt
        import time

        headers = {
            'alg': 'ES256',
            'kid': private_key.thumbprint()
        }

        payload = {
            'iss': 'test-client',
            'iat': int(time.time()),
            'exp': int(time.time()) + 300
        }

        token = jwt.encode(headers, payload, private_key)
        print("✅ Private key signing works")

        # Verify with public key
        decoded = jwt.decode(token, public_jwk)
        print("✅ Public key verification works")

        print()
        print("🎉 Keypair is valid and working!")
        print()
        print("📝 Next steps:")
        print("1. Copy the CLIENT_SECRET_JWK value above to your .env file")
        print("2. Restart your application")
        print("3. Test the OAuth flow with: curl http://localhost:5001/oauth/client-metadata.json")

    except Exception as e:
        print(f"❌ Error generating keypair: {e}")
        sys.exit(1)

def validate_existing_jwk():
    """Validate existing JWK in environment."""
    print("🔍 Validating existing CLIENT_SECRET_JWK...")

    jwk_json = os.getenv('CLIENT_SECRET_JWK')
    if not jwk_json:
        print("❌ CLIENT_SECRET_JWK not found in environment")
        print("💡 Run this script without arguments to generate a new keypair")
        sys.exit(1)

    try:
        jwk = JsonWebKey.import_key(jwk_json)

        # Check key type and algorithm
        if jwk.get('kty') != 'EC':
            print("❌ Key is not EC type")
            sys.exit(1)

        if jwk.get('crv') != 'P-256':
            print("❌ Key is not P-256 curve")
            sys.exit(1)

        # Test signing/verification
        test_message = b"test"

        from authlib.jose import jwt
        import time

        headers = {
            'alg': 'ES256',
            'kid': jwk.thumbprint()
        }

        payload = {
            'iss': 'test-client',
            'iat': int(time.time()),
            'exp': int(time.time()) + 300
        }

        token = jwt.encode(headers, payload, jwk)

        # Get public key for verification
        public_jwk = json.loads(jwk.as_json(is_private=False))
        decoded = jwt.decode(token, public_jwk)

        print("✅ Existing JWK is valid and working!")
        print(f"📋 Key ID (thumbprint): {jwk.thumbprint()}")

    except Exception as e:
        print(f"❌ Invalid JWK: {e}")
        print("💡 Run this script without arguments to generate a new keypair")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--validate":
        validate_existing_jwk()
    else:
        generate_client_jwk()
