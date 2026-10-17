from base64 import b64encode
from time import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


class AuthIntent:
    @staticmethod
    def _export_public_key_spki(public_key) -> str:
        spki_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return b64encode(spki_bytes).decode("utf-8")

    @staticmethod
    def _sign(private_key, data: bytes) -> str:
        signature = private_key.sign(data, ec.ECDSA(hashes.SHA256()))
        return b64encode(signature).decode("utf-8")

    @staticmethod
    def get_auth_intent(session) -> dict | None:

        try:
            private_key = ec.generate_private_key(ec.SECP256R1())
            public_key = private_key.public_key()

            client_public_key = AuthIntent._export_public_key_spki(public_key)
            client_epoch_timestamp = str(int(time()))

            response = session.get(
                "https://apis.roblox.com/hba-service/v1/getServerNonce"
            )
            server_nonce = response.text.strip('"')

            payload = f"{client_public_key}|{client_epoch_timestamp}|{server_nonce}"
            sai_signature = AuthIntent._sign(private_key, payload.encode("utf-8"))

            return {
                "clientEpochTimestamp": client_epoch_timestamp,
                "clientPublicKey": client_public_key,
                "saiSignature": sai_signature,
                "serverNonce": server_nonce,
            }
        except Exception:
            return None