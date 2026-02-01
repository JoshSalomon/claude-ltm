# Delete a Memory

Delete a memory from the Long-Term Memory system.

## Usage

- `/forget <id>` - Delete a memory by its ID

## Instructions

Arguments: $ARGUMENTS

**If no ID provided**:
Ask the user: "Which memory would you like to delete? Please provide the memory ID (e.g., mem_abc12345)"

**If ID is provided**:
1. First, call `mcp__ltm__get_memory` to retrieve and show the memory to the user
2. Ask for confirmation: "Are you sure you want to delete this memory? (yes/no)"
3. If confirmed, call `mcp__ltm__forget` with the memory ID
4. Confirm deletion to the user

**Note**: The memory will be archived before deletion, so it can potentially be recovered if needed.
