
import re
import filehash as fh
import json

from pathlib import Path
from PIL import Image
from PIL import ExifTags
from datetime import datetime as dt

class PhotoOrganiser:

    def __init__(self,
                 src_dir,
                 dst_dir,
                 supportd_types,
                 ignored_types):
        self.src_dir = Path(src_dir)
        self.dst_dir = Path(dst_dir)
        self.supportd_types = set(map(lambda s: s.lower(), supportd_types))
        self.ignored_types = set(map(lambda s: s.lower(), ignored_types))

        self.existing_files = {}
        self.new_files = {}


    def scan_dst(self, force_rescan = False):
        self.existing_files = {}

        json_file_path = self.dst_dir / '.phorg.dstdata'
        files_to_be_skipped = set([str(json_file_path)])

        if not force_rescan:
            if json_file_path.exists():
                with open(json_file_path, 'r') as f:
                    self.existing_files = json.load(f)

                files_to_be_skipped.update([p for pl in self.existing_files.values() for p in pl])

        paths = sorted(list(self.dst_dir.rglob("*")))
        path_index = 1
        for path in paths:

            print('Scanning destination directory: [%d/%d]'%(path_index, len(paths)), end="\r", flush=True)
            path_index = path_index + 1

            if path.is_dir() \
                or path.name in files_to_be_skipped \
                or path.suffix.lower() not in self.supportd_types \
                or path.name.startswith('._'):
                continue

            file_hash = fh.get_file_hash(path)
            if file_hash in self.existing_files:
                if path.name not in self.existing_files[file_hash]:
                    self.existing_files[file_hash].append(path.name)
            else:
                self.existing_files[file_hash] = [path.name]

        with open(json_file_path, 'w') as f:
            json.dump(self.existing_files, f)


    def scan_src(self):
        self.processed_dirs = []
        self.dst_to_src_dict = {}
        self.ignored_files = []
        self.existing_duplicate_files = {}
        self.new_duplicate_files = {}
        self.new_files = {}
        self.unsupported_files = []
        self.unsupported_exts = set()
        self.error_files = []

        paths = sorted(list(self.src_dir.rglob('*')))
        path_index = 1
        for path in paths:

            print('Scanning source directory: [%d/%d]'%(path_index, len(paths)), end="\r", flush=True)
            path_index = path_index + 1

            if path.is_dir():
                self.processed_dirs.append(path)
                continue

            ext = path.suffix.lower()
            if (ext in self.supportd_types):
                src_file_hash = fh.get_file_hash(path)

                if src_file_hash in self.existing_files:
                    self.existing_duplicate_files[path] = self.existing_files[src_file_hash]

                elif src_file_hash in self.new_files:
                    self.new_duplicate_files[path] = self.new_files[src_file_hash]

                else:
                    try:
                        image_dst_path = self.__get_image_dst_path(path)

                        while True:
                            if image_dst_path not in self.dst_to_src_dict:
                                self.dst_to_src_dict[image_dst_path] = path
                                self.new_files[src_file_hash] = str(path)
                                break

                            next_image_name = self.__get_next_image_name(image_dst_path.stem)
                            image_dst_path = image_dst_path.with_name(next_image_name).with_suffix(ext)

                    except:
                        self.error_files.append(path)
            elif ext in self.ignored_types:
                self.ignored_files.append(path)
            else:
                self.unsupported_files.append(path)
                self.unsupported_exts.add(ext)


    def move(self):
        for dst, src in self.dst_to_src_dict.items():
            src.rename(dst)
            file_hash = list(self.new_files.keys())[list(self.new_files.values()).index(str(src))]
            if file_hash in self.existing_files:
                if dst.name not in self.existing_files[file_hash]:
                    self.existing_files[file_hash].append(dst.name)
            else:
                self.existing_files[file_hash] = [dst.name]

        json_file_path = self.dst_dir / '.phorg.dstdata'
        with open(json_file_path, 'w') as f:
            json.dump(self.existing_files, f)


    def write_summary(self, file_path):
        with open(file_path, "w") as of:

            of.write(dt.strftime(dt.now(),  "%Y-%m-%d %H:%M:%S"))

            of.write('\n\nMoving images')
            of.write('\n  from: ' + str(self.src_dir))
            of.write('\n    to: ' + str(self.dst_dir))

            of.write(f'\n\nProcessed directories: [{len(self.processed_dirs)}]\n')
            of.write('\n'.join('    ../' + str(p.relative_to(self.src_dir)) for p in sorted(self.processed_dirs)))

            of.write(f'\n\nMoved file: [{len(self.dst_to_src_dict)}]\n')
            of.write('\n'.join('    ../' + str(d.relative_to(self.dst_dir)) + ' <- ../' + str(s.relative_to(self.src_dir)) for d, s in sorted(self.dst_to_src_dict.items())))

            of.write(f'\n\nUnsupported extensions: [{len(self.unsupported_exts)}]\n')
            of.write('\n'.join('    ' + str(p) for p in sorted(self.unsupported_exts)))

            of.write(f'\n\nUnsupported file: [{len(self.unsupported_files)}]\n')
            of.write('\n'.join('    ../' + str(p.relative_to(self.src_dir)) for p in sorted(self.unsupported_files)))

            of.write(f'\n\nErroneous file: [{len(self.error_files)}]\n')
            of.write('\n'.join('    ../' + str(p.relative_to(self.src_dir)) for p in sorted(self.error_files)))

            of.write(f'\n\nExisting Duplicate file: [{len(self.existing_duplicate_files)}]\n')
            of.write('\n'.join('    ../' + str(s.relative_to(self.src_dir)) + ' = ' + str([Path(p).name for p in c]) for s, c in sorted(self.existing_duplicate_files.items())))

            of.write(f'\n\nNew Duplicate file: [{len(self.new_duplicate_files)}]\n')
            of.write('\n'.join('    ../' + str(s.relative_to(self.src_dir)) + ' = ' + str(Path(c).relative_to(self.src_dir)) for s, c in sorted(self.new_duplicate_files.items())))

            of.write(f'\n\nIgnored file: [{len(self.ignored_files)}]\n')
            of.write('\n'.join('    ../' + str(p.relative_to(self.src_dir)) for p in sorted(self.ignored_files)))


    def __get_image_dst_path(self, image_path):
        exif = self.__get_exif(image_path)
        image_name = self.__exif_2_name(exif) + image_path.suffix.lower()
        return self.dst_dir.joinpath(image_name)


    @staticmethod
    def __get_exif(image_path):
        i = Image.open(image_path)
        exif = {
            ExifTags.TAGS[k] : v
            for k, v in i._getexif().items()
            if k in ExifTags.TAGS
            }
        return exif


    @staticmethod
    def __exif_2_name(exif):
        idt = dt.strptime(exif['DateTime'], '%Y:%m:%d %H:%M:%S')
        sdt = dt.strftime(idt, '%Y%m%d_%H%M%S')

        make = exif.get('Make')
        if make:
            make = re.sub(re.compile(r'\s+'), '', make)
        else:
            make = 'Unknown'

        model = exif.get('Model')
        if model:
            model = re.sub(re.compile(r'\s+'), '', model)
        else:
            model = 'Camera'
        return sdt + '_' + make + '_' + model


    @staticmethod
    def __get_next_image_name(image_name):
        parts = image_name.split('_')
        if len(parts) < 4 or 5 < len(parts):
            raise ValueError('Invalid file name: ' + image_name)
        elif len(parts) == 4:
            parts.insert(2, '0')
        else:
            parts[2] = str(int(parts[2]) + 1)
        return '_'.join(parts)

