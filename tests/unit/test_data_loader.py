import io
import pandas as pd
import pytest
from tools.data_loader import load_dataset

def test_load_csv_and_hash():
    loaded = load_dataset(b"id,value\n1,10\n2,20\n", "sample.csv")
    assert loaded.frame.shape == (2, 2)
    assert len(loaded.sha256) == 64
    assert loaded.file_extension == ".csv"

def test_reject_unsupported_extension():
    with pytest.raises(ValueError, match="Unsupported file type"):
        load_dataset(b"a\n1\n", "sample.txt")

def test_reject_empty_and_oversized_file():
    with pytest.raises(ValueError, match="empty"):
        load_dataset(b"", "empty.csv")
    with pytest.raises(ValueError, match="upload limit"):
        load_dataset(b"a" * 11, "large.csv", max_file_size=10)

def test_reject_duplicate_headers():
    with pytest.raises(ValueError, match="Duplicate column names"):
        load_dataset(b"value,value\n1,2\n", "duplicate.csv")

def test_load_xlsx():
    raw_buffer = io.BytesIO()
    pd.DataFrame({"id": [1, 2], "value": [3.5, 4.5]}).to_excel(raw_buffer, index=False, engine="openpyxl")
    loaded = load_dataset(raw_buffer.getvalue(), "sample.xlsx")
    assert loaded.frame.shape == (2, 2)
