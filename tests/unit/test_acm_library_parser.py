"""ACM library files are third-party XML, so every parse must refuse entity declarations.

A "billion laughs" DTD in a library (or in the FT View SE symbol SVG embedded in one, or in
the extracted ``.object_nibs`` / ``.subobjects`` side files) must raise ``EntitiesForbidden``
instead of expanding into gigabytes of memory.
"""

from pathlib import Path
from xml.sax.saxutils import escape

import pytest
from defusedxml import EntitiesForbidden

from bin.logic_acm_library_parser import acm_library_parser, get_object_NIBS, get_subobjects

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_LIBRARIES = sorted((REPO_ROOT / "acm_libraries" / "ApplicationCodeManagerLibraries").glob("*.HSL4"))

BILLION_LAUGHS_DTD = """<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol2 "&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
  <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
  <!ENTITY lol5 "&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;">
  <!ENTITY lol6 "&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;">
  <!ENTITY lol7 "&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;">
  <!ENTITY lol8 "&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;">
  <!ENTITY lol9 "&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;">
]>
"""


def _library(symbol_value='<group width="40" height="20"/>', prolog=""):
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        + prolog
        + '<Library><DefinitionData Id="DefinitionDataABC-123">'
        '<Obj><Par Name="Cfg_Time" DType="Real" DVal="&amp;lol9;"/></Obj>'
        '<SObjs><SObj Name="Sub1" DispName="Sub 1"><Par Name="Index" DType="Int"/></SObj></SObjs>'
        '<NIBS><NIB Name="Nib1" Value="1"/></NIBS>'
        "<FTView><Collections><Collection Name=\"SE Symbols\"><Items>"
        '<Item Name="Sym1"><Attributes><Attribute Name="Icons"><Value>'
        + escape(symbol_value)
        + "</Value></Attribute></Attributes></Item>"
        "</Items></Collection></Collections></FTView>"
        "</DefinitionData></Library>"
    )


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_benign_library_still_parses(tmp_path):
    parser = acm_library_parser(_write(tmp_path, "Lib.HSL4", _library()))

    assert parser.get_library_ID() == "ABC-123"
    assert parser.get_parameters()["Cfg_Time"]["DVal"] == "&lol9;"
    assert parser.extract_all_ft_view_se_symbols()[0]["Width"] == 40

    parser.extract_object_NIBS(str(tmp_path))
    parser.extract_subobjects(str(tmp_path))
    library_path = str(tmp_path / "Lib.HSL4")
    assert get_object_NIBS(library_path) == {"Nib1": {"Name": "Nib1", "Value": "1"}}
    assert set(get_subobjects(library_path)) == {"Sub1"}


@pytest.mark.parametrize("library", SHIPPED_LIBRARIES, ids=lambda p: p.name)
def test_shipped_libraries_still_parse(library, tmp_path):
    parser = acm_library_parser(str(library))

    assert parser.get_library_ID()
    assert parser.get_parameters()
    parser.extract_all_ft_view_se_symbols()
    parser.extract_object_NIBS(str(tmp_path))
    get_object_NIBS(str(tmp_path / library.name))


def test_billion_laughs_library_is_rejected(tmp_path):
    path = _write(tmp_path, "Evil.HSL4", _library(prolog=BILLION_LAUGHS_DTD))

    with pytest.raises(EntitiesForbidden):
        acm_library_parser(path)


def test_external_entity_library_is_rejected(tmp_path):
    secret = _write(tmp_path, "secret.txt", "top secret")
    prolog = f'<!DOCTYPE Library [<!ENTITY xxe SYSTEM "file://{secret}">]>\n'
    path = _write(tmp_path, "Xxe.HSL4", _library(prolog=prolog))

    with pytest.raises(EntitiesForbidden):
        acm_library_parser(path)


def test_billion_laughs_in_embedded_symbol_svg_is_rejected(tmp_path):
    svg = BILLION_LAUGHS_DTD + '<group width="40" height="20">&lol9;</group>'
    parser = acm_library_parser(_write(tmp_path, "EvilSymbol.HSL4", _library(symbol_value=svg)))

    with pytest.raises(EntitiesForbidden):
        parser.extract_all_ft_view_se_symbols()


@pytest.mark.parametrize(
    ("loader", "suffix", "root"),
    [(get_object_NIBS, ".object_nibs", "NIBS"), (get_subobjects, ".subobjects", "SObjs")],
)
def test_billion_laughs_in_extracted_side_files_is_rejected(tmp_path, loader, suffix, root):
    _write(tmp_path, "Evil" + suffix, BILLION_LAUGHS_DTD + f'<{root}><X Name="&lol9;"/></{root}>')

    with pytest.raises(EntitiesForbidden):
        loader(str(tmp_path / "Evil.HSL4"))
