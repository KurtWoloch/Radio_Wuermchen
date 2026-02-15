# unescape_log.py

import sys

def unescape_log_content(input_file_path, output_file_path):
    """
    Reads a file containing log data and un-escapes common character sequences,
    treating the input as a string literal (e.g., from a JSON log entry).
    
    Specifically replaces:
    - '\\n' with a newline character (\n)
    - '\\\\' with a single backslash (\\)
    - '\"' with a double quote (")
    """
    try:
        with open(input_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: Input file not found at {input_file_path}")
        return

    # 1. Replace escaped newlines with actual newlines
    # Note: Python's raw string decoding handles this, but since the input is text, 
    # we manually replace the string literal '\n' with the character '\n'
    content = content.replace('\\n', '\n')
    
    # 2. Replace escaped backslashes with single backslashes
    # We must do this *after* the newline replacement to avoid problems if the 
    # log already contained literal newlines that were double-escaped.
    # We do not need to replace double-escaped backslashes with single ones
    # if the input is a standard string from a log. Let's focus on the common issue.
    # The most stable way to un-escape JSON strings is to load them, but 
    # since you're passing a whole file that may contain non-JSON text, 
    # we'll use string replacements focused on common literal escapes.
    
    # Replace literal backslashes (\) with a single backslash:
    content = content.replace('\\\\', '\\') 
    
    # Replace escaped quotes with literal quotes (if needed, typically done by a JSON parser)
    content = content.replace('\\"', '"')

    # The user asked for '\r' replacement, which usually signifies a carriage return.
    # This might be tricky if it's meant to be a literal return.
    # Assuming '\r' in the log means actual carriage return:
    content = content.replace('\\r', '\r')
    
    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Successfully un-escaped content and wrote to {output_file_path}")
    except Exception as e:
        print(f"Error writing output file: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python unescape_log.py <input_file_path> <output_file_path>")
        sys.exit(1)
        
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    
    unescape_log_content(input_path, output_path)