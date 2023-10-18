import os
import requests
from sphinx.locale import __
from sphinx.errors import SphinxError

def check_file_exist(local_path, url):
    if not os.path.isfile(local_path):

        if not url:
            raise SphinxError(
                __(f'Failed to read {local_path}, please use `url` to specify the location')
            )

        response = requests.get(url)
        if response.status_code == 200:
            with open(local_path, "wb") as file:
                file.write(response.content)
        else:
            raise SphinxError(
                __(f'Failed to download {url}')
            )
