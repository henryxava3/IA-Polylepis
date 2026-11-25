import pytest
from app.sources import doi_value, license_value, normalized, relevant, reconstruct_abstract, public_url
from app.ingestion import occurrence_values, split_text


@pytest.mark.parametrize(('raw','expected'), [
    ('https://doi.org/10.1234/EXAMPLE', '10.1234/example'),
    (' DOI: 10.12345/test ', '10.12345/test'),
    ('https://example.org/10.1234/test', None), ('not a doi', None), (None, None),
])
def test_doi_normalization(raw, expected):
    assert doi_value(raw) == expected


@pytest.mark.parametrize(('raw','expected'), [
    ('cc-by', 'cc-by'), ('https://creativecommons.org/licenses/by/4.0/', 'cc-by'),
    ('https://creativecommons.org/licenses/by-sa/4.0/', 'cc-by-sa'),
    ('https://creativecommons.org/publicdomain/zero/1.0/', 'cc0'),
    ('https://evil.example/licenses/by/4.0', None), ('cc-by-nc', None), ('open-access', None), (None, None),
])
def test_licenses_fail_closed(raw, expected):
    assert license_value(raw) == expected


def test_taxon_relevance_avoids_common_name_false_positive():
    assert relevant('Ecología de Polylepis')
    assert relevant('Bosques andinos', 'Polylepis was sampled')
    assert not relevant('Hotel Yagual y turismo')
    assert not relevant('Otherpolylepis examples')
    assert not relevant('Effects of a Chrysochromulina polylepis bloom')
    assert not relevant('Rhododendron polylepis Franch.')
    assert not relevant('Dendroaspis Polylepis venom')
    assert relevant('Polylepis forest restoration in the Andes')


def test_multilingual_normalization():
    assert normalized('QUEÑUA: Ecología—2020') == 'quenua ecologia2020'


def test_abstract_original_order():
    assert reconstruct_abstract({'tree': [1], 'A': [0], 'grows.': [2]}) == 'A tree grows.'


@pytest.mark.parametrize('url', ['http://example.com/a.pdf', 'https://127.0.0.1/file', 'https://localhost/file', 'https://user:password@example.com/a.pdf', 'https://example.com:8000/a.pdf', 'file:///etc/passwd'])
def test_pdf_url_local_and_non_https_denied(url, monkeypatch):
    monkeypatch.setattr('app.sources.socket.getaddrinfo', lambda *a, **kw: [(2, 1, 6, '', ('127.0.0.1', 443))])
    assert not public_url(url)


def test_chunks_remain_exact_substrings():
    original = 'Texto sintético para probar fragmentación. ' * 80
    parts = list(split_text(original))
    assert len(parts) > 1
    assert all(part in original and len(part) <= 650 for part in parts)
    assert parts[-1].endswith('fragmentación.')


def example_occurrence():
    # Deliberately synthetic, never inserted into the user's scientific corpus.
    return {'key': 1, 'genus': 'Polylepis', 'occurrenceStatus': 'PRESENT',
            'decimalLatitude': -12, 'decimalLongitude': -75, 'scientificName': 'Polylepis TEST FIXTURE',
            'datasetKey': 'synthetic-test', 'coordinateUncertaintyInMeters': 0}


def test_unknown_uncertainty_is_null_not_zero():
    values = occurrence_values(example_occurrence())
    assert values[8] is None


@pytest.mark.parametrize('field,value', [('decimalLatitude', 100), ('decimalLongitude', float('nan')), ('genus', 'Other'), ('occurrenceStatus', 'ABSENT')])
def test_bad_occurrence_is_excluded(field, value):
    row = example_occurrence()
    row[field] = value
    assert occurrence_values(row) is None


def test_gbif_detected_vocabulary_is_supported():
    row = example_occurrence()
    row['occurrenceStatus'] = 'DETECTED'
    assert occurrence_values(row) is not None
