from django.core.management.base import BaseCommand
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import os

class Command(BaseCommand):
    help = 'Generate RSA keys for OpenID Connect'

    def handle(self, *args, **options):
        # Create keys directory if it doesn't exist
        keys_dir = 'keys'
        if not os.path.exists(keys_dir):
            os.makedirs(keys_dir)

        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        # Get private key in PEM format
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        # Get public key in PEM format
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        # Save keys in the keys directory
        private_key_path = os.path.join(keys_dir, 'private_key.pem')
        public_key_path = os.path.join(keys_dir, 'public_key.pem')

        with open(private_key_path, 'wb') as f:
            f.write(private_pem)
        with open(public_key_path, 'wb') as f:
            f.write(public_pem)

        self.stdout.write(
            self.style.SUCCESS(f'Successfully generated RSA keys in {keys_dir} directory')
        )