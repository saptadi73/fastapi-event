"""Generate the merchant RSA key pair required by DOKU SNAP sandbox."""
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main() -> None:
    target = (Path(__file__).resolve().parents[1] / ".secrets").resolve()
    target.mkdir(parents=True, exist_ok=True)
    private_path = target / "doku-snap-private.pem"
    public_path = target / "doku-snap-public.pem"
    if private_path.exists() or public_path.exists():
        raise SystemExit("DOKU SNAP key files already exist; refusing to overwrite them")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    public_path.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    print(f"Private key created at {private_path} (keep secret)")
    print(f"Public key created at {public_path} (upload this one to DOKU)")


if __name__ == "__main__":
    main()
