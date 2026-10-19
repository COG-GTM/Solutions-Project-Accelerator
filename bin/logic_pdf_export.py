import os
import sys
from typing import List

from pypdf import PdfWriter
from pypdf.annotations import Link, Text
from pypdf.generic import ArrayObject, Fit, NameObject, NumberObject

from bin.logic_pdf_text import page_matrices

# The icon box is 18x18 points, anchored 1 point in from the requested point.
TEXT_ANNOT_SIZE = 18.0
TEXT_ANNOT_INSET = 1.0


def _page_geometry(page):
    """Return (derotation matrix, rotated width, rotated height, mediabox).

    The caller supplies fractions of the rotation-adjusted page rectangle, so the
    fractions are scaled by the rotated size and then derotated back into unrotated
    mediabox space.
    """
    mediabox = page.mediabox
    mw, mh = float(mediabox.width), float(mediabox.height)
    rotation = int(page.rotation or 0) % 360
    derotation = page_matrices(rotation, mw, mh)[0]
    width, height = (mh, mw) if rotation in (90, 270) else (mw, mh)
    return derotation, width, height, mediabox


def _to_pdf_point(x, y, derotation, mediabox):
    """Map a top-left-origin point in page space to PDF user space."""
    a, b, c, d, e, f = derotation
    ux, uy = a * x + c * y + e, b * x + d * y + f
    return float(mediabox.left) + ux, float(mediabox.top) - uy


class pdf_with_data_exporter():
    """
    A class to export data to a PDF document.
    """
    
    def __init__(self, pdf_path) -> None:
        """
        Initialize the PDF document.

        :param pdf_path: The path to the PDF document.
        :type pdf_path: str

        :return: None
        :rtype: None

        This function initializes the PDF document by opening the document at the specified path.
        """
        self.__path = pdf_path
        self.__doc = PdfWriter(clone_from=pdf_path)


    def get_number_of_pages(self):
        """
        Get the number of pages in the PDF document.

        :return: The number of pages in the PDF document.
        :rtype: int

        This function returns the number of pages in the PDF document.
        """
        return len(self.__doc.pages)


    def create_page_link(self, pno: int,rect:List[float],to_pno:int):
        """
        Creates a link on a specific page of a PDF document.
        :param pno: The page number of the source page.
        :type pno: int
        :param rect: The coordinates of the rectangle where the link will be placed.
        :type rect: List[float]
        :param to_pno: The page number of the target page.
        :type to_pno: int
        :returns: None
        :rtype: None

        This function creates a link on a specific page of a PDF document. The link is positioned using the provided coordinates on the page. The target page is also specified.

        Example:
            >>> create_page_link(0, (50, 100, 150, 150), 1)
            None
        """
        page = self.__doc.pages[pno]
        derotation, width, height, mediabox = _page_geometry(page)

        x0, y0 = _to_pdf_point(rect[0] * width, rect[1] * height, derotation, mediabox)
        x1, y1 = _to_pdf_point(rect[2] * width, rect[3] * height, derotation, mediabox)

        link = Link(rect=(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)),
                    target_page_index=to_pno,
                    fit=Fit.xyz(left=0, top=0, zoom=0))
        added = self.__doc.add_annotation(page_number=pno, annotation=link)
        # pypdf resolves the deferred destination to a bare page NUMBER, which is
        # only legal in a remote go-to. A /Dest in this document must name the page.
        added[NameObject('/Dest')] = ArrayObject([
            self.__doc.pages[to_pno].indirect_reference,
            NameObject('/XYZ'), NumberObject(0), NumberObject(0), NumberObject(0)])
        
    def save_pdf(self):
        """
        Save the PDF.

        :return: None
        :rtype: None

        This function saves the PDF document.
        """
        self.__doc.write(self.__path)

    def export_pdf(self, path):
        """
        Export the document as a PDF file.

        :param path: The path where the PDF file will be saved.
        :type path: str

        :return: None
        :rtype: None

        This function exports the document as a PDF file and saves it at the specified path.
        """
        self.__doc.write(path)

    def create_annotation(self, pno: int,point:List[float],name:str,description:str):
        """
        Creates an annotation on a specific page of the document.

        :param pno: The page number where the annotation will be created.
        :type pno: int
        :param point: The coordinates of the annotation on the page, as a list of two floats representing the x and y values.
        :type point: List[float]
        :param name: The name of the annotation.
        :type name: str
        :param description: The description of the annotation.
        :type description: str
        :return: None
        :rtype: None

        This function creates an annotation on a specific page of the document. The annotation is positioned using the provided coordinates on the page. The name and description of the annotation are also provided.
        
        Example:
            >>> create_annotation(1, [0.5, 0.5], "Annotation 1", "This is an example annotation")
        """
        page = self.__doc.pages[pno]
        derotation, width, height, mediabox = _page_geometry(page)

        x, y = _to_pdf_point(point[0] * width, point[1] * height, derotation, mediabox)

        annotation = Text(rect=(x + TEXT_ANNOT_INSET,
                                y - TEXT_ANNOT_INSET - TEXT_ANNOT_SIZE,
                                x + TEXT_ANNOT_INSET + TEXT_ANNOT_SIZE,
                                y - TEXT_ANNOT_INSET),
                          text=name)
        annotation[NameObject('/Name')] = NameObject('/Tag')
        self.__doc.add_annotation(page_number=pno, annotation=annotation)
        



if __name__ == '__main__':
    # Usage: python -m bin.logic_pdf_export <pdf_path>, or set SPA_SAMPLE_PDF.
    sample_pdf = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('SPA_SAMPLE_PDF')
    if not sample_pdf:
        sys.exit('No PDF supplied. Pass a path as the first argument or set SPA_SAMPLE_PDF.')

    pdf_exporter = pdf_with_data_exporter(sample_pdf)
    #pdf_exporter.create_page_link(0,(50,100,150,150))
    pdf_exporter.create_annotation(0,[0,0],'','')
