import pytest
from langflow.type_extraction.type_extraction import extract_inner_type

@pytest.mark.parametrize(
    "return_type, expected",
    [
        # Happy path - lowercase list
        ("list[str]", "str"),
        ("list[int]", "int"),
        ("list[bool]", "bool"),

        # Happy path - uppercase List
        ("List[str]", "str"),
        ("LIST[int]", "int"),

        # Nested lists
        ("list[list[str]]", "list[str]"),
        ("List[List[int]]", "List[int]"),

        # Complex inner types
        ("list[dict[str, int]]", "dict[str, int]"),
        ("list[Union[str, int]]", "Union[str, int]"),

        # Empty inner type
        ("list[]", ""),

        # Non-list types (should return as-is)
        ("str", "str"),
        ("int", "int"),
        ("dict[str, int]", "dict[str, int]"),
        ("set[int]", "set[int]"),
        ("Union[str, list[int]]", "Union[str, list[int]]"),

        # Invalid list syntax
        ("list[str", "list[str"),
        ("list str]", "list str]"),
    ],
)
def test_extract_inner_type(return_type: str, expected: str):
    """Test extract_inner_type with various type string formats."""
    assert extract_inner_type(return_type) == expected
