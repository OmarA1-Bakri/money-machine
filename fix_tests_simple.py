#!/usr/bin/env python3
"""Add required fields to test Job and WorkflowRun creations."""

import re
from pathlib import Path


def fix_file(filepath: Path) -> None:
    """Fix test file by adding required NOT NULL fields."""
    content = filepath.read_text()
    
    # Add Shop to imports if needed
    if ", Shop" not in content and "from money_machine.persistence.tables import" in content:
        content = content.replace(
            "from money_machine.persistence.tables import",
            "from money_machine.persistence.tables import Shop,"
        )
    
    lines = content.split('\n')
    new_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        
        # Add Shop creation before WorkflowRun if not already present
        if '    workflow_id = uuid4()' in line:
            # Look back to see if Shop was already added
            lookback = '\n'.join(new_lines[-20:])
            if 'shop_id = uuid4()' not in lookback:
                indent = ' ' * (len(line) - len(line.lstrip()))
                new_lines.insert(-1, f'{indent}shop_id = uuid4()')
                new_lines.insert(-1, f'{indent}shop = Shop(')
                new_lines.insert(-1, f'{indent}    id=shop_id,')
                new_lines.insert(-1, f'{indent}    name="test-shop",')
                new_lines.insert(-1, f'{indent}    provider_shop_id="test-provider-id",')
                new_lines.insert(-1, f'{indent}    connection_state="ACTIVE",')
                new_lines.insert(-1, f'{indent}    timezone="UTC",')
                new_lines.insert(-1, f'{indent})')
                new_lines.insert(-1, f'{indent}session.add(shop)')
                new_lines.insert(-1, '')
        
        # Add shop_id to WorkflowRun if missing
        if 'WorkflowRun(' in line and i + 1 < len(lines) and 'id=workflow_id' in lines[i+1]:
            if 'shop_id' not in lines[i+2]:
                indent = ' ' * (len(lines[i+1]) - len(lines[i+1].lstrip()))
                new_lines.append(f'{indent}shop_id=shop_id,')
        
        # Add object fields to Job if missing
        if 'Job(' in line and i + 1 < len(lines) and 'id=' in lines[i+1]:
            # Find the line with job_type
            for j in range(i+1, min(i+10, len(lines))):
                if 'job_type=' in lines[j] and 'object_type' not in lines[j+1]:
                    indent = ' ' * (len(lines[j]) - len(lines[j].lstrip()))
                    # We'll add these after job_type line
                    new_lines.append(lines[i+1])  # id line
                    new_lines.append(lines[i+2])  # workflow_id line
                    new_lines.append(lines[j])     # job_type line
                    new_lines.append(f'{indent}object_type="workflow_runs",')
                    new_lines.append(f'{indent}object_id=workflow_id,')
                    # Skip the lines we already added
                    i = j
                    break
        
        i += 1
    
    new_content = '\n'.join(new_lines)
    
    if new_content != content:
        filepath.write_text(new_content)
        print(f"Modified {filepath.name}")
    else:
        print(f"No changes for {filepath.name}")


def main():
    """Fix test files."""
    for test_file in [
        Path("/workspace/tests/integration/orchestration/test_dependency_resolver.py"),
        Path("/workspace/tests/integration/orchestration/test_scheduler.py"),
    ]:
        if test_file.exists():
            print(f"\nProcessing {test_file}...")
            fix_file(test_file)


if __name__ == "__main__":
    main()
