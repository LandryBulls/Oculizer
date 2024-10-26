import os
import time
import platform
from pathlib import Path
from datetime import datetime, timedelta

def get_creation_time(path):
    """
    Get the creation time of a file in a cross-platform way.
    
    Args:
        path (Path): Path object to get creation time for
        
    Returns:
        float: The creation timestamp of the file
    """
    stat = path.stat()
    if platform.system() == 'Windows':
        return stat.st_ctime
    else:
        try:
            # Try to get birth time (creation time) on Unix systems
            return stat.st_birthtime
        except AttributeError:
            # Fallback to ctime if birthtime is not available
            return stat.st_ctime

def format_timestamp(timestamp):
    """Format a timestamp into a readable string."""
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

def list_recent_files(directory_path, hours=24):
    """
    Lists all files in the specified directory that were created in the last specified hours.
    
    Args:
        directory_path (str): Path to the directory to scan
        hours (int): Number of hours to look back (default: 24)
    """
    directory = Path(directory_path)
    cutoff_time = time.time() - (hours * 3600)
    recent_files = []
    
    print(f"\nFiles created in the last {hours} hours in {directory_path}:")
    print("-" * 80)
    print(f"{'Filename':<40} | {'Created':<19} | {'Modified':<19} | {'Size':>10}")
    print("-" * 80)
    
    for file_path in directory.rglob('*'):
        if file_path.is_file():
            creation_time = get_creation_time(file_path)
            mod_time = file_path.stat().st_mtime
            
            if creation_time > cutoff_time:
                recent_files.append(file_path)
                
                # Get file size
                size = file_path.stat().st_size
                size_str = f"{size:,} B" if size < 1024 else f"{size/1024:,.1f} KB"
                
                print(f"{file_path.name[:39]:<40} | "
                      f"{format_timestamp(creation_time)} | "
                      f"{format_timestamp(mod_time)} | "
                      f"{size_str:>10}")
    
    print("-" * 80)
    print(f"Total files found: {len(recent_files)}")
    return recent_files

def delete_recent_files(directory_path, hours=24, dry_run=True):
    """
    Deletes all files in the specified directory that were created in the last specified hours.
    
    Args:
        directory_path (str): Path to the directory to scan
        hours (int): Number of hours to look back (default: 24)
        dry_run (bool): If True, only simulates deletion (default: True)
    """
    recent_files = list_recent_files(directory_path, hours)
    
    if not recent_files:
        print("\nNo files found to delete.")
        return
    
    print("\n" + ("DRY RUN - No files will be deleted" if dry_run else "DELETING FILES"))
    print("-" * 80)
    
    for file_path in recent_files:
        creation_time = format_timestamp(get_creation_time(file_path))
        if dry_run:
            print(f"Would delete: {file_path} (Created: {creation_time})")
        else:
            try:
                file_path.unlink()
                print(f"Deleted: {file_path} (Created: {creation_time})")
            except Exception as e:
                print(f"Error deleting {file_path}: {str(e)}")
    
    print("-" * 80)
    print(f"Total files {'that would be' if dry_run else ''} deleted: {len(recent_files)}")

if __name__ == "__main__":
    # Example usage for listing files:
    print("LISTING RECENT FILES:")
    list_recent_files("./song_data")
    
    print("\nDELETION SIMULATION:")
    # Example usage for deleting files (with dry_run=True for safety)
    delete_recent_files("./song_data", dry_run=True)
    
    # To actually delete files, you would use:
    # delete_recent_files("./song_data", dry_run=False)