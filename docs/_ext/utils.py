import os
import requests
from sphinx.locale import __
from sphinx.errors import SphinxError

def check_file_exist(path, url):
    if not os.path.isfile(path):

        if not url:
            raise SphinxError(
                __(f'Failed to read {path}, please use `url` to specify the location')
            )

        response = requests.get(url)
        if response.status_code == 200:
            print(f"Under {os.getcwd()}. Downloading {url} to {path}")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as file:
                file.write(response.content)
        else:
            raise SphinxError(
                __(f'Failed to download {url}')
            )
