import os

def get_lti_config() -> dict:
    issuer = os.getenv("LTI_ISSUER", "https://moodle.example.edu")
    return {
        issuer: [{
            "default": True,
            "client_id": os.getenv("LTI_CLIENT_ID", ""),
            "auth_login_url": os.getenv("LTI_AUTH_LOGIN_URL", ""),
            "auth_token_url": os.getenv("LTI_AUTH_TOKEN_URL", ""),
            "key_set_url": os.getenv("LTI_KEY_SET_URL", ""),
            "deployment_ids": [os.getenv("LTI_DEPLOYMENT_ID", "1")],
        }]
    }
