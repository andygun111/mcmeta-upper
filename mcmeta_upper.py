import os
import json
import shutil
import zipfile
import ctypes
from ctypes import wintypes

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

def recycle_file(path):
    if os.name == 'nt':
        try:
            # go into windows shell to recycle without needing send2trash pip package because i dont like packages
            class SHFILEOPSTRUCTW(ctypes.Structure):
                _fields_ = [
                    ("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT),
                    ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
                    ("fFlags", wintypes.WORD), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", wintypes.LPVOID), ("lpszProgressTitle", wintypes.LPCWSTR)
                ]
            pFrom = ctypes.create_unicode_buffer(os.path.abspath(path) + '\0\0')
            fileop = SHFILEOPSTRUCTW(
                hwnd=None, wFunc=3, pFrom=ctypes.cast(pFrom, wintypes.LPCWSTR),
                pTo=None, fFlags=0x40 | 0x10 | 0x04, fAnyOperationsAborted=False,
                hNameMappings=None, lpszProgressTitle=None
            )
            res = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(fileop))
            return res == 0 and not fileop.fAnyOperationsAborted
        except Exception:
            return False
    else:
        return False

def get_copy_name(filepath):
    base, ext = os.path.splitext(filepath)
    i = 1
    new_path = f"{base} ({i}){ext}"
    while os.path.exists(new_path):
        i += 1
        new_path = f"{base} ({i}){ext}"
    return new_path

def modify_mcmeta(meta_path, max_version):
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if 'pack' in data:
            pack = data['pack']
            old_fmt = pack.get('pack_format', pack.get('format', None))
            
            if 'max_format' not in pack:
                if 'pack_format' in pack:
                    del pack['pack_format']
                if 'format' in pack:
                    del pack['format']
                
                pack['min_format'] = old_fmt if old_fmt is not None else 1
                pack['max_format'] = int(max_version)
                
                pack['supported_formats'] = {
                    "min_inclusive": pack['min_format'],
                    "max_inclusive": pack['max_format']
                }
            else:
                pack['max_format'] = int(max_version)
                if 'supported_formats' in pack and isinstance(pack['supported_formats'], dict):
                    pack['supported_formats']['max_inclusive'] = int(max_version)
                elif 'supported_formats' in pack and isinstance(pack['supported_formats'], list) and len(pack['supported_formats']) == 2:
                    pack['supported_formats'][1] = int(max_version)

        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
        return True
    except Exception as e:
        print(f"  -> Failed to parse json in {meta_path}: {e}")
        return False

def run_process(target_folder, overwrite_files, max_version, modify_folders, recycle_mode):
    print("\nStarting")
    items = os.listdir(target_folder)

    for item in items:
        item_path = os.path.join(target_folder, item)
        
        # do zips
        if os.path.isfile(item_path) and item.endswith('.zip'):
            temp_dir = os.path.join(target_folder, f"_temp_{item[:-4]}")
            try:
                with zipfile.ZipFile(item_path, 'r') as zf:
                    zf.extractall(temp_dir)

                mcmeta_found = False
                mod_failed = False
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        if file == 'pack.mcmeta':
                            mcmeta_found = True
                            if not modify_mcmeta(os.path.join(root, file), max_version):
                                mod_failed = True

                if not mcmeta_found:
                    shutil.rmtree(temp_dir)
                    print(f"[{item}] ignored, no pack.mcmeta found inside")
                    continue
                    
                if mod_failed:
                    shutil.rmtree(temp_dir)
                    print(f"[{item}] ABORTED! failed to parse/modify mcmeta. original file is untouched.")
                    continue

                new_zip_base = os.path.join(target_folder, f"_temp_zip_{item[:-4]}")
                shutil.make_archive(new_zip_base, 'zip', temp_dir)
                temp_zip = new_zip_base + '.zip'
                shutil.rmtree(temp_dir)

                if not overwrite_files:
                    copy_name = get_copy_name(item_path)
                    os.rename(temp_zip, copy_name)
                    print(f"[{item}] had copy made ({os.path.basename(copy_name)})")
                else:
                    trash_success = False
                    if recycle_mode:
                        trash_success = recycle_file(item_path)
                    else:
                        try:
                            os.remove(item_path)
                            trash_success = True
                        except:
                            pass

                    if not trash_success:
                        copy_name = get_copy_name(item_path)
                        os.rename(temp_zip, copy_name)
                        print(f"[{item}] couldn't be {'recycled' if recycle_mode else 'deleted'}, made a copy instead")
                    else:
                        os.rename(temp_zip, item_path)
                        print(f"[{item}] was overwritten successfully")
                        
            except Exception as e:
                print(f"[{item}] failed with error: {e}")
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)

    # do folders
    if modify_folders:
        for item in items:
            item_path = os.path.join(target_folder, item)
            if os.path.isdir(item_path) and not item.startswith("_temp_"):
                try:
                    if not overwrite_files:
                        copy_name = get_copy_name(item_path)
                        shutil.copytree(item_path, copy_name)
                        
                        mcmeta_found = False
                        mod_failed = False
                        for root, dirs, files in os.walk(copy_name):
                            for file in files:
                                if file == 'pack.mcmeta':
                                    mcmeta_found = True
                                    if not modify_mcmeta(os.path.join(root, file), max_version):
                                        mod_failed = True
                                        
                        if not mcmeta_found:
                            shutil.rmtree(copy_name)
                            print(f"[{item} (folder)] ignored, no pack.mcmeta found")
                        elif mod_failed:
                            shutil.rmtree(copy_name)
                            print(f"[{item} (folder)] aborted, failed to modify mcmeta, no copy was made")
                        else:
                            print(f"[{item} (folder)] had copy made ({os.path.basename(copy_name)})")
                    else:
                        # do it the ocky way
                        temp_dir = os.path.join(target_folder, f"_temp_folder_{item}")
                        shutil.copytree(item_path, temp_dir)
                        
                        mcmeta_found = False
                        mod_failed = False
                        for root, dirs, files in os.walk(temp_dir):
                            for file in files:
                                if file == 'pack.mcmeta':
                                    mcmeta_found = True
                                    if not modify_mcmeta(os.path.join(root, file), max_version):
                                        mod_failed = True

                        if not mcmeta_found:
                            shutil.rmtree(temp_dir)
                            print(f"[{item} (folder)] ignored, no pack.mcmeta found")
                            continue
                            
                        if mod_failed:
                            shutil.rmtree(temp_dir)
                            print(f"[{item} (folder)] aborted, failed to modify mcmeta, no overwrite was done")
                            continue
                            
                        trash_success = False
                        if recycle_mode:
                            trash_success = recycle_file(item_path)
                        else:
                            try:
                                shutil.rmtree(item_path)
                                trash_success = True
                            except:
                                pass
                                
                        if not trash_success:
                            print(f"[{item} (folder)] couldn't remove original folder, leaving modified copy as {os.path.basename(temp_dir)}")
                        else:
                            os.rename(temp_dir, item_path)
                            print(f"[{item} (folder)] was safely overwritten successfully")
                            
                except Exception as e:
                    print(f"[{item} (folder)] failed: {e}")

    print("\Done! Press enter to return")
    input()

def main():
    target_folder = os.getcwd()
    overwrite_files = True
    max_version = 10000
    modify_folders = False
    recycle_mode = True

    while True:
        clear()
        action_word = "OVERWRITE" if overwrite_files else "CREATE COPIES OF"
        
        print('-- Minecraft MCMETA version increaser')
        print('- To remove the "This is for an earlier version" annoying popup every time you swap in the pack...')
        print('- Packs changed with this only work on 1.21.9+')
        print()
        print(f'Will: {action_word} all resource pack ZIPs in {target_folder} to make their max version {max_version}')
        print()
        
        print('1: Start')
        print(f'2: Change folder (currently: {target_folder})')
        over_copy_str = "overwrite" if overwrite_files else "copies"
        print(f'3: Change to Overwrite files vs. Create copies (currently: {over_copy_str})')
        print(f'4: Change max version to (currently: {max_version})')
        mod_fold_str = "yes, modify raw folders too" if modify_folders else "no, only ZIPs"
        print(f'5: Also modify folders (currently: {mod_fold_str})')
        
        rec_del_str = "recycle" if recycle_mode else "delete"
        if not overwrite_files:
            print(f'//6: When overwriting, Recycle vs. Delete (currently: {rec_del_str}) (but you arent overwriting)')
        else:
            print(f'6: When overwriting, Recycle vs. Delete (currently: {rec_del_str})')

        choice = input('\n> ').strip()

        if choice == '1':
            clear()
            print("-- Confirm your settings...")
            print(f"- Folder: {target_folder}")
            print(f"- Mode: {'overwrite files' if overwrite_files else 'create copies'}")
            if overwrite_files:
                print(f"- Trash method: {'recycle bin' if recycle_mode else 'permanent delete'}")
            print(f"- Setting to max version: {max_version}")
            print(f"- Modifying raw folders too: {'yes' if modify_folders else 'no'}")
            print("\nStart? (y/n)")
            
            conf = input("> ").strip().lower()
            if conf == 'y':
                run_process(target_folder, overwrite_files, max_version, modify_folders, recycle_mode)
                
        elif choice == '2':
            new_folder = input("Type new path: ").strip()
            if os.path.exists(new_folder) and os.path.isdir(new_folder):
                target_folder = new_folder
            else:
                print("Invalid path. defaulting back to script folder...")
                target_folder = os.getcwd()
                
        elif choice == '3':
            overwrite_files = not overwrite_files
            
        elif choice == '4':
            try:
                max_version = int(input("Type new max version number: ").strip())
            except ValueError:
                pass
                
        elif choice == '5':
            modify_folders = not modify_folders
            
        elif choice == '6':
            if overwrite_files:
                recycle_mode = not recycle_mode

if __name__ == "__main__":
    main()