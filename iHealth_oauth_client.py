#! iHealth_oauth_client.py

import base64, requests

class oAuthClient:
    """
    A class to handle OAuth client credentials flow.
    """
    
    def __init__(self, token_url):
        """
        Initialize the OAuth client with the token endpoint URL.

        :param token_url: The URL to which the OAuth credentials will be sent.
        """
        self.token_url = token_url

    def get_auth_token(self, client_id, client_secret):
        """
        Retrieve an access token by sending client credentials to the token endpoint.

        :param client_id: The OAuth client ID.
        :param client_secret: The OAuth client secret.
        :return: The access token if successful, None otherwise.
        """
        u_auth_coded = base64.b64encode(bytes(client_id + ':' + client_secret, 'utf-8'))
        u_auth = u_auth_coded.decode()
        data = {
            'grant_type': 'client_credentials',
            'scope': 'ihealth'
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'authorization': 'Basic ' + str(u_auth),
            'cache-control': 'no-cache',
            'accept': 'application/json'        
        }

        try:
            response = requests.post(self.token_url, data=data, headers=headers)
            response.raise_for_status()
            return response.json().get('access_token')
        except requests.exceptions.RequestException as e:
            print(f"Error retrieving auth token: {e}")
            return None

