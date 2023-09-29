from docutils import nodes
from docutils.parsers.rst import directives

from sphinx.locale import _, __
from sphinx.util.docutils import SphinxDirective
from sphinx.directives.patches import Figure
from sphinx.errors import SphinxError

from os import path
from functools import reduce
import hashlib

from pdf2image import convert_from_path

class PDFViewError(SphinxError):
    category = 'PDFView error'


def image_location(argument, default=''):
    return directives.get_measure(argument, ['', 'px', '%'])

def loc_normalize(loc, edge=0):
    if loc.endswith('%'):
        return float(loc[:-1]) / 100 * edge
    elif loc.endswith('px'):
        return float(loc[:-2])
    else:
        val = float(loc)
        if val < 1:
            return val * edge
        else:
            return val

def image_relocate(loc, width=0, height=0):
    left = loc_normalize(loc[0], width)
    upper = loc_normalize(loc[1], height)
    right = loc_normalize(loc[2], width)
    lower = loc_normalize(loc[3], height)
    return (min(left, right), min(upper, lower), max(left, right), max(upper, lower))

class PDFViewDirective(Figure):
    required_arguments = 2
    optional_arguments = 0
    has_content = True

    option_spec = Figure.option_spec.copy()
    option_spec['left'] = image_location
    option_spec['upper'] = image_location
    option_spec['right'] = image_location
    option_spec['lower'] = image_location

    def run(self):
        pdf_relative_path = self.arguments[0]
        try:
            pdf_page = int(self.arguments[1])
        except ValueError:
            raise PDFViewError(
                __(f'PDFView only accepts integer page number, recieving {self.arguments[1]}')
            )
        if pdf_page <= 0:
            raise PDFViewError(
                __(f'PDFView only accepts positive page number, recieving {pdf_page}')
            )
        if not pdf_relative_path.lower().endswith('pdf'):
            raise PDFViewError(
                __(f'PDFView only accepts PDF file, recieving {pdf_relative_path}')
            )

        (doc_path, doc_line) = self.state_machine.get_source_and_line()
        doc_dir = path.split(doc_path)[0]
        pdf_path = path.normpath(path.join(doc_dir, pdf_relative_path))

        # TODO: page render cache
        
        images = convert_from_path(pdf_path, first_page=pdf_page, last_page=pdf_page)
        
        loc = [
            self.options.pop('left', None),
            self.options.pop('upper', None),
            self.options.pop('right', None),
            self.options.pop('lower', None)
        ]

        if reduce(lambda a, b: a and b, loc):
            width, height = images[0].size
            target_image = images[0].crop(image_relocate(loc, width, height))
            suffix = f'.{pdf_page}.{hashlib.md5((doc_path+str(doc_line)+"".join(loc)).encode("utf8")).hexdigest()}.png'
            image_relative_page = pdf_relative_path + suffix
            image_path = pdf_path + suffix
        else:
            target_image = images[0]
            image_relative_page = pdf_relative_path + f'.{pdf_page}.png'
            image_path = pdf_path + f'.{pdf_page}.png'

        target_image.save(image_path,"PNG")
        self.arguments[0] = image_relative_page

        return super().run()

def setup(app):
    app.add_directive('pdfview', PDFViewDirective)

    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
