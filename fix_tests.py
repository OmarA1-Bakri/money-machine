#!/usr/bin/env python3
"""Fix test files to add required NOT NULL fields for Job and WorkflowRun."""

import re
from pathlib import Path


def fix_test_file(filepath: Path) -> None:
    """Fix a single test file by adding required fields."""
    content = filepath.read_text()
    original_content = content

    # Add Shop import if not present
    if "from money_machine.persistence.tables import" in content and "Shop" not in content:
        content = re.sub(
            r"from money_machine\.persistence\.tables import (.+?)(?:\n|$)",
            lambda m: f"from money_machine.persistence.tables import {m.group(1).rstrip()}, Shop\n" if "Shop" not in m.group(1) else m.group(0),
            content,
        )

    # Pattern to match test functions
    test_func_pattern = r"@pytest\.mark\.asyncio\s+async def (test_\w+)\(session: AsyncSession\):"

    # Find all test functions
    test_functions = re.finditer(test_func_pattern, content)
    offsets = []
    
    for match in test_functions:
        func_start = match.end()
        # Look ahead to find the first WorkflowRun creation
        workflow_match = re.search(
            r'(\s+)workflow_id = uuid4\(\)\s+workflow = WorkflowRun\(',
            content[func_start:func_start+2000]
        )
        if workflow_match:
            insertion_point = func_start + workflow_match.start()
            indent = workflow_match.group(1)
            
            # Check if Shop creation already exists before this point
            preceding_text = content[func_start:insertion_point]
            if "shop = Shop(" not in preceding_text:
                shop_creation = f'''{indent}shop_id = uuid4()
{indent}shop = Shop(
{indent}    id=shop_id,
{indent}    name="test-shop",
{indent}    provider_shop_id="test-provider-id",
{indent}    connection_state="ACTIVE",
{indent}    timezone="UTC",
{indent})
{indent}session.add(shop)

'''
                offsets.append((insertion_point, shop_creation))

    # Apply insertions in reverse order to maintain offsets
    for offset, text in reversed(offsets):
        content = content[:offset] + text + content[offset:]

    # Add shop_id to WorkflowRun creations that don't have it
    content = re.sub(
        r'WorkflowRun\(\s+id=workflow_id,\s+workflow_type=',
        'WorkflowRun(\n        id=workflow_id,\n        shop_id=shop_id,\n        workflow_type=',
        content
    )

    # Add object_type and object_id to Job creations that don't have them
    # Pattern: Job( followed by id=, workflow_id=, job_type=
    content = re.sub(
        r'(Job\(\s+id=\w+,\s+workflow_id=workflow_id,\s+job_type="[^"]+",)\s+status=',
        r'\1\n        object_type="workflow_runs",\n        object_id=workflow_id,\n        status=',
        content
    )

    # Handle cases where Job has id from a variable
    content = re.sub(
        r'(Job\(\s+id=\w+,\s+workflow_id=workflow_id,\s+job_type="\w+",)\s+status=',
        r'\1\n        object_type="workflow_runs",\n        object_id=workflow_id,\n        status=',
        content
    )

    if content != original_content:
        filepath.write_text(content)
        print(f"Fixed {filepath}")
    else:
        print(f"No changes needed for {filepath}")


def main():
    """Fix all test files in tests/integration/orchestration/."""
    test_dir = Path("/workspace/tests/integration/orchestration")
    
    for test_file in test_dir.glob("test_*.py"):
        if "dependency_resolver" in test_file.name or "scheduler" in test_file.name:
            print(f"\nProcessing {test_file.name}...")
            fix_test_file(test_file)


if __name__ == "__main__":
    main()
