"""
Main git-search-replace module
"""

from optparse import OptionParser
import subprocess
import sys
import re
import os
import bisect
import fnmatch
import json
from datetime import datetime

SEARCH_JSON_FILENAME = "search_matches.json"
MATCHES_JSON_FILENAME = "matches.json"
RESULTS_FOLDER_NAME = "search-results"

def update_search_json(filename, match_entries, repo_root_folder, branch):
    data = load_json_list(filename)

    # Try to find existing entry for this repo
    existing = next((d for d in data if d.get("repository") == repo_root_folder and d.get("branch") == branch), None)

    if not existing:
        existing = {
            "repository": repo_root_folder,
            "branch": branch,
            "changes": []
        }
        data.append(existing)

    current_entries = existing["changes"]

    existing_serialized = {json.dumps(e, sort_keys=True) for e in current_entries}

    for entry in match_entries:
        serialized = json.dumps(entry, sort_keys=True)
        if serialized not in existing_serialized:
            current_entries.append(entry)
            existing_serialized.add(serialized)

    save_json_list(filename, data)

def load_json_list(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_json_list(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def run_subprocess(cmd):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return result.stdout

def log(msg):
    sys.stderr.write(msg + "\n")

def error(s):
    log("git-search-replace: error: " + s)
    sys.exit(-1)

class Expression(object):
    def __init__(self, fromexpr, toexpr, big_g):
        self.fromexpr = fromexpr
        self.toexpr = toexpr
        self.big_g = big_g

def underscore_to_titlecase(name):
    l = []
    for p in name.split('_'):
        if p:
            p = p[:1].upper() + p[1:]
        l.append(p)
    return ''.join(l)

def titlecase_to_underscore(name):
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()

class GitSearchReplace(object):
    """Main class"""

    def __init__(self, fix=None, renames=None, filters=None, expressions=None):
        self.fix = fix
        self.renames = renames
        self.filters = filters
        self.expressions_str = expressions
        self.expressions = []
        self.stage = None
        self.search_json_filename = self.get_timestamped_filename(SEARCH_JSON_FILENAME)
        self.matches_json_filename = self.get_timestamped_filename(MATCHES_JSON_FILENAME)
        results_dir = os.path.join(self.get_parent_of_git_root(), RESULTS_FOLDER_NAME)
        os.makedirs(results_dir, exist_ok=True)
        self.search_json_path = os.path.join(results_dir, self.search_json_filename)
        self.matches_json_path = os.path.join(results_dir, self.matches_json_filename)

    BIG_G_REGEX = re.compile(r"[\]G[{][^}]*[}]")
    def calc_big_g(self, big_g_expr):
        r"""Transform the special interpolated \G{<python>}"""
        parts = []
        prefix = r'\G{'
        oparts = big_g_expr.split(prefix)
        parts = [oparts[0]]
        for part in oparts[1:]:
            if '}' in part:
                x = part.find('}')
                parts.append(prefix + part[:x+1])
                parts.append(part[x+1:])
            else:
                parts.append(part)

        def replacer_func(G):
            def m(i):
                return G.groups(0)[i]
            gen = []
            dotslash = '/'
            if self.stage == 'content':
                dotslash = '.'
            namespace = dict(
                G=G,
                m=m,
                underscore_to_titlecase=underscore_to_titlecase,
                titlecase_to_underscore=titlecase_to_underscore,
                dotslash=dotslash,
            )
            for part in parts:
                if part.startswith(r'\G{'):
                    gen.append(eval(part[3:-1:], namespace))
                else:
                    gen.append(part)
            return ''.join(gen)
        return replacer_func

    def compile_expressions(self):
        if not self.expressions_str:
            error("no FROM-TO expressions specified")
            return

        expressions = []
        pairs = list(zip(self.expressions_str[::2], self.expressions_str[1::2]))

        for fromexpr, toexpr in pairs:
            big_g = None
            if self.BIG_G_REGEX.search(toexpr):
                big_g = self.calc_big_g(toexpr)
            from_regex = re.compile(fromexpr)
            expressions.append(Expression(from_regex, toexpr, big_g))
        self.expressions = expressions

    def get_parent_of_git_root(self):
        git_root = self.get_git_root()
        parent_folder = os.path.dirname(git_root)
        return parent_folder

    def get_git_root(self):
        if not hasattr(self, '_git_root'):
            git_root_bytes = run_subprocess(["git", "rev-parse", "--show-toplevel"])
            self._git_root = git_root_bytes.decode('utf-8').strip()
        return self._git_root

    def get_git_branch(self):
        if not hasattr(self, '_git_branch'):
            branch_bytes = run_subprocess(["git", "rev-parse", "--abbrev-ref", "HEAD"])
            self._git_branch = branch_bytes.decode("utf-8").strip()
        return self._git_branch

    def get_git_root_relative(self, filename):
        git_root = self.get_git_root()
        repo_root_folder = os.path.basename(git_root)
        rel_path_inside_repo = os.path.relpath(filename, git_root).replace('\\', '/')
        return f"{repo_root_folder}/{rel_path_inside_repo}"

    def sub(self, expr, content, stage):
        self.stage = stage
        if expr.big_g:
            return expr.fromexpr.sub(expr.big_g, content)
        return expr.fromexpr.sub(expr.toexpr, content)

    def search_replace_in_files(self):
        self.total_matches_found = 0
        git_root = self.get_git_root()
        filenames = str(run_subprocess(["git", "ls-files"]), 'utf-8').splitlines()
        log(f"\n=== Running git-search-replace in repository: '{git_root}' ===\n")
        filtered_filenames = []
        for filename in filenames:
            matching_filters = [
                (mode, pattern) for (mode, pattern) in self.filters
                if fnmatch.fnmatch(filename, pattern)
            ]
            if matching_filters:
                # Pick the most specific (longest pattern)
                mode, _ = max(matching_filters, key=lambda x: len(x[1]))
                if mode == 'exclude':
                    continue
            filtered_filenames.append(filename)

        for filename in filtered_filenames:
            if not os.path.isfile(filename):
                continue
            with open(filename, "rb") as fileobj:
                original_bytes = fileobj.read()

            # Try decoding (but keep raw bytes untouched)
            try:
                filedata = original_bytes.decode("utf-8")
                original_encoding = "utf-8"
            except UnicodeDecodeError:
                filedata = original_bytes.decode("latin-1")
                original_encoding = "latin-1"

            if self.fix:
                self.show_file(filename, filedata, original_bytes, original_encoding, git_root)
            else:
                self.show_lines_grep_like(filename, filedata, git_root)

        log(f"\n=== Total matches found across all files: {self.total_matches_found} ===\n")

        if self.renames:
            for filename in filtered_filenames:
                for expr in self.expressions:
                    new_filename = filename
                    new_filename = self.sub(expr, new_filename, 'filename')
                    if new_filename != filename:
                        log("")
                        log("rename-src-file: %s" % (filename, ))
                        log("rename-dst-file: %s" % (new_filename, ))
                        if self.fix:
                            dirname = os.path.dirname(new_filename)
                            if dirname and not os.path.exists(dirname):
                                os.makedirs(dirname)
                            cmd = ["git", "mv", filename, new_filename]
                            run_subprocess(cmd)

    def print_matches_for_expr(self, filename, content, expr):
        lines = content.splitlines()
        line_starts = []
        pos = 0
        for line in lines:
            line_starts.append(pos)
            pos += len(line) + 1

        matches = expr.fromexpr.finditer(content)
        matches_lines = []

        git_root = self.get_git_root()
        repo_root_folder = os.path.basename(git_root)
        rel_path_inside_repo = os.path.relpath(filename, git_root).replace('\\', '/')
        rel_filename = repo_root_folder + '/' + rel_path_inside_repo

        for match in matches:
            line_nr = bisect.bisect(line_starts, match.start())
            matches_lines.append(f"{rel_filename}:{line_nr + 1}:_{lines[line_nr - 1]}")

        matches_lines.sort()
        for line in matches_lines:
            log(line)

    def show_file(self, filename, filedata, original_bytes, original_encoding, git_root):
        rel_filename = self.get_git_root_relative(filename)
        repo_root_folder = os.path.basename(git_root)

        new_filedata = filedata
        for expr in self.expressions:
            new_filedata = self.sub(expr, new_filedata, 'content')

        if new_filedata != filedata:
            match_entries = []

            log(f"--- Matches BEFORE change in {rel_filename} ---")
            for expr in self.expressions:
                lines_before = filedata.splitlines(keepends=True)
                lines_after = new_filedata.splitlines(keepends=True)
                line_starts = []
                pos = 0
                for line in lines_before:
                    line_starts.append(pos)
                    pos += len(line)

                matches = list(expr.fromexpr.finditer(filedata))
                for match in matches:
                    line_nr = max(0, bisect.bisect_right(line_starts, match.start()) - 1)
                    old_line = lines_before[line_nr]
                    new_line = lines_after[line_nr]

                    replaced_substr = match.group()
                    replacement_substr = expr.toexpr

                    log(f"{rel_filename}:{line_nr + 1}:_{old_line.rstrip()}")
                    match_entries.append({
                        "filename": rel_filename,
                        "line": line_nr + 1,
                        "before": old_line,
                        "after": new_line,
                        "changed_text": {
                            "old": replaced_substr,
                            "new": replacement_substr
                        }
                    })

            self.total_matches_found += len(match_entries)

            if self.fix:    
                if new_filedata != filedata:

                    new_bytes = new_filedata.encode(original_encoding, errors="replace")

                    if new_bytes != original_bytes:
                        with open(filename, "w", encoding=original_encoding, newline='') as fileobj:
                            fileobj.write(new_filedata)

            log(f"\n--- Matches AFTER change in {rel_filename} ---")
            for entry in match_entries:
                log(f"{entry['filename']}:{entry['line']}:_{entry['after'].rstrip()}")
            log("")

            if self.fix:
                update_search_json(self.matches_json_path, match_entries, repo_root_folder, self.get_git_branch())

    def show_lines_grep_like(self, filename, filedata, git_root):
        rel_filename = self.get_git_root_relative(filename)
        repo_root_folder = os.path.basename(git_root)

        new_filedata = filedata
        expr_id = 0
        shown_lines = []
        match_entries = []

        for expr in self.expressions:
            lines_before = filedata.splitlines(keepends=True)
            line_pos = []
            pos = 0
            for line in lines_before:
                line_pos.append(pos)
                pos += len(line)

            matches = list(expr.fromexpr.finditer(filedata))
            
            for match in matches:
                line_nr = max(0, bisect.bisect_right(line_pos, match.start()) - 1)
                old_line = lines_before[line_nr]
                replaced_substr = match.group()

                shown_lines.append(f"{rel_filename}:{line_nr + 1}:{expr_id * '_'}{old_line.rstrip()}")

                match_entries.append({
                    "filename": rel_filename,
                    "line": line_nr + 1,
                    "before": old_line,
                    "changed_text": {
                        "old": replaced_substr
                    }
                })

            new_filedata = self.sub(expr, new_filedata, 'content')
            expr_id += 1

        if shown_lines:
            
            log(f"--- Matches in {rel_filename} ---")
            
            shown_lines.sort()
            for line in shown_lines:
                log(line)
            log("")

            if match_entries:
                self.total_matches_found += len(match_entries)

                update_search_json(self.search_json_path, match_entries, repo_root_folder, self.get_git_branch())

    def get_timestamped_filename(self, base_name):
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        name, ext = os.path.splitext(base_name)
        return f"{name}-{timestamp}{ext}"

    def run(self):
        self.compile_expressions()
        self.search_replace_in_files()

def add_filter(option, opt_str, value, parser, mode):
    if not hasattr(parser.values, 'filters'):
        parser.values.filters = []
    parser.values.filters.append((mode, value))

def get_script_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

default_search_config = os.path.join(get_script_dir(), "config", "gsr-config.json")
default_filetypes_config = os.path.join(get_script_dir(), "config", "gsr-filetypes-config.json")

def main():
    """Main function"""
    parser = OptionParser(usage=
            "usage: %prog [options] (FROM-SEPARATOR-TO...)\n"
            "       %prog [options] -p FROM1 TO1  FROM2 TO2 ...")

    parser.add_option("-f", "--fix",
        action="store_true", dest="fix", default=False,
        help="Perform changes in-place")

    parser.add_option("-e", "--exclude",
        action="callback", callback=add_filter,
        callback_args=('exclude', ),
        type="string",
        metavar="PATTERN",
        help="Exclude files matching the provided globbing "
             "pattern (can be specified more than once)")

    parser.add_option("-i", "--include",
        action="callback", callback=add_filter,
        callback_args=('include', ),
        type="string",
        metavar="PATTERN",
        help="Include files matching the provided globbing "
             "pattern (can be specified more than once)")

    parser.add_option("-n", "--no-renames",
        action="store_false", dest="renames", default=True,
        help="Don't perform renames")
    
    parser.add_option("-c", "--search-config",
        dest="search_config",
        metavar="PATH",
        default=default_search_config,
        help="Path to search config file (default: ./config/gsr-config.json)")

    parser.add_option("-t", "--filetypes-config",
        dest="filetypes_config",
        metavar="PATH",
        default=default_filetypes_config,
        help="Path to filetypes config file (default: ./config/gsr-filetypes-config.json)")

    (options, args) = parser.parse_args()

    filters = getattr(options, 'filters', [])

    # Validate filetypes config
    filetypes_path = options.filetypes_config
    if not os.path.isfile(filetypes_path):
        error(f"filetypes config file not found: {filetypes_path}")
    with open(filetypes_path, "r", encoding="utf-8") as f:
        try:
            filetypes_data = json.load(f)
            for entry in filetypes_data:
                pattern = entry.get("fileType")
                mode = entry.get("option", "include").lower()
                if pattern and mode in ("include", "exclude"):
                    filters.append((mode, pattern))
        except json.JSONDecodeError:
            error(f"invalid JSON in filetypes config: {filetypes_path}")

    if len(filters) >= 1:
        if filters[0][0] == 'include':
            filters = [('exclude', '**')] + filters

    # Conflict detection: same fileType with both include/exclude
    conflict_check = {}
    for mode, pattern in filters:
        if pattern not in conflict_check:
            conflict_check[pattern] = set()
        conflict_check[pattern].add(mode)

    for pattern, modes in conflict_check.items():
        if "include" in modes and "exclude" in modes:
            error(f"Conflicting include/exclude for pattern: {pattern}")

    expressions = []
    # Validate search config
    search_config_path = options.search_config
    if not os.path.isfile(search_config_path):
        error(f"search config file not found: {search_config_path}")

    with open(search_config_path, "r", encoding="utf-8") as f:
        config_data = json.load(f)  # ← This is where config_data is defined

    for entry in config_data:
        raw_old = re.escape(entry["OldString"])
        new = entry["NewString"]
        match_type = entry.get("Match", "").lower()

        if match_type == "full":
            old = f"^{raw_old}$"
        elif match_type == "left":
            old = f"^{raw_old}"
        elif match_type == "right":
            old = f"{raw_old}$"
        else:
            old = raw_old

        expressions.extend([old, new])
        
        sys.stderr.write(
            f"\033[93mPreparing search-replace: '{entry['OldString']}' -> '{entry['NewString']}' (Match: {match_type})\033[0m\n"
        )

    gsr = GitSearchReplace(
        fix=options.fix,
        renames=options.renames,
        filters=filters,
        expressions=expressions)
    gsr.run()

    import gc
    gc.collect()

__all__ = ["main"]