from docutils import nodes
from docutils.parsers.rst import directives

from sphinx.locale import _, __
from sphinx.directives.code import LiteralInclude
from sphinx.errors import SphinxError

from utils import check_file_exist

import json

class RemoteCodeError(SphinxError):
    category = 'RemoteCode error'

def remotecode_type(argument):
    type_list = ['raw', 'github-permalink']
    return 'raw' if argument.strip() not in type_list else argument.strip()

def download_name_raw(name):
    return name

def download_github_permalink(name):
    return f"{name}.json"

download_name_dict = {
    'raw': download_name_raw,
    'github-permalink': download_github_permalink
}

class RemoteCodeDirective(LiteralInclude):
    has_content = True
    option_spec = LiteralInclude.option_spec.copy()
    option_spec['url'] = directives.path
    option_spec['type'] = remotecode_type

    def run(self):
        file_type = self.options.pop('type', 'raw')
        url = self.options.pop('url', None)
        (rel_path, abs_path) = self.env.relfn2path(self.arguments[0])
        download_path = download_name_dict[file_type](abs_path)
        check_file_exist(download_path, url)

        if file_type == 'github-permalink':
            with open(download_path, "r") as json_file:
                data = json.load(json_file)
                if "payload" in data and "blob" in data["payload"] and "rawLines" in data["payload"]["blob"]:
                    raw = data["payload"]["blob"]["rawLines"]
                else:
                    raise RemoteCodeError(
                        __(f'Invalid Github permalink {url}')
                    )

                with open(abs_path, "w") as output_file:
                    output_file.write('\n'.join(raw))

            anno = url.split('/')[-1]
            highlight_lines = []
            if '#' in anno:
                highlight = anno.split('#')[-1].replace('L', '').split('-')
                try:
                    if len(highlight) == 1:
                        highlight_lines.append(int(highlight[0]))
                    else:
                        start = int(highlight[0])
                        end = int(highlight[1]) + 1
                        if start > end:
                            raise ValueError
                        highlight_lines.extend(range(start, end))
                except ValueError:
                        raise RemoteCodeError(
                            __(f'Invalid Github permalink {url}')
                        )
                
                if 'lines' in self.options and 'lineno-match' in self.options:
                    lines = self.options['lines']
                    starts = []
                    for group in lines.split(','):
                        starts.append(int(group.split('-')[0]))
                    
                    highlight_lines = [x - min(starts) + 1 for x in highlight_lines]
                
                if 'emphasize-lines' not in self.options:
                    self.options['emphasize-lines'] = ','.join([str(x) for x in highlight_lines])

            if 'caption' in self.options:
                if self.options.get('caption', None):
                    self.options['caption'] = f"{self.options['caption']} `🌏 <{url}>`_"
                else:
                    self.options['caption'] = f"`{anno.split('#')[0].split('?')[0]} <{url}>`_"
                
        return super().run()


def setup(app):
    app.add_directive('remotecode', RemoteCodeDirective)

    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
