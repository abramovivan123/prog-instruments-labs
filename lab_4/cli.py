import argparse
import sys

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

from config_loader import (
    ALL_MODIFICATIONS,
    CONFIG,
    DEFAULT_ALGORITHM,
    DEFAULT_EXPERIMENT_COUNT,
    HASH_PREVIEW_LENGTH,
    IDEAL_AVALANCHE_PERCENT,
    MIN_EXPERIMENT_COUNT,
    MODIFICATION_TYPES,
    PROGRESS_BAR_LENGTH,
    PROGRESS_NCOLS,
    SUPPORTED_ALGORITHMS,
)
from hash_core import (
    AvalancheResult,
    compute_hash,
    get_avalanche_quality,
    run_experiments,
    summarize_results,
)

_use_color = True


def cli_config(*keys):
    value = CONFIG["cli"]
    for key in keys:
        value = value[key]
    return value


def _c(color_name: str, text: str) -> str:
    if not _use_color:
        return text
    code = cli_config("ansi_codes", color_name)
    return f"\033[{code}m{text}\033[0m"


def green(text: str) -> str:
    return _c("green", text)


def yellow(text: str) -> str:
    return _c("yellow", text)


def cyan(text: str) -> str:
    return _c("cyan", text)


def bold(text: str) -> str:
    return _c("bold", text)


def red(text: str) -> str:
    return _c("red", text)


def dim(text: str) -> str:
    return _c("dim", text)


def color_for_percent(percent: float):
    quality = get_avalanche_quality(percent)
    match quality.level:
        case "excellent":
            return green
        case "moderate":
            return yellow
        case _:
            return red


def print_banner():
    print(cyan(cli_config("banner")))


def print_hash_pair(
    label: str,
    result: AvalancheResult,
    algorithm: str,
):
    labels = cli_config("labels")
    print(f"  {bold(label)}")
    print(f"    {labels['source_text']} : {dim(repr(result.original_text))}")
    print(f"    {labels['modified_text']}     : {yellow(repr(result.modified_text))}")
    original_preview = dim(result.original_hash[:HASH_PREVIEW_LENGTH])
    modified_preview = yellow(result.modified_hash[:HASH_PREVIEW_LENGTH])
    print(f"    {algorithm.upper()} до     : {original_preview}…")
    print(f"    {algorithm.upper()} после  : {modified_preview}…")

    filled = int(PROGRESS_BAR_LENGTH * result.diff_percent / 100)
    bar = green("█" * filled) + dim("░" * (PROGRESS_BAR_LENGTH - filled))
    color = color_for_percent(result.diff_percent)
    print(
        f"    {labels['bit_difference']}   : [{bar}] "
        f"{color(f'{result.diff_percent:.1f}%')} "
        f"({result.changed_bits} / {result.total_bits})"
    )
    print()


def print_summary_table(summary: dict, algorithm: str):
    labels = cli_config("labels")
    table = cli_config("table")

    print(bold("\n" + table["summary_top"]))
    print(bold(table["summary_title"]))
    print(bold(table["summary_bottom"]))
    print(f"  {labels['algorithm']}       : {cyan(algorithm.upper())}")
    print(f"  {labels['experiments']}  : {summary['total_experiments']}")
    avg_color = color_for_percent(summary["avg_diff_percent"])
    print(f"  {labels['average_percent']}      : {avg_color(str(summary['avg_diff_percent']))}")
    print(f"  {labels['min_percent']}         : {summary['min_diff_percent']}")
    print(f"  {labels['max_percent']}        : {summary['max_diff_percent']}")
    print(f"  {labels['average_bits']}      : {summary['avg_changed_bits']} / {summary['total_bits']}")
    print()

    mod_width = table["modification_column_width"]
    pct_width = table["percent_column_width"]
    print(f"  {labels['modification_type']:<{mod_width}} {labels['average_difference_percent']:>{pct_width}}")
    print(f"  {'─' * table['separator_length']}")
    for mod, pct in summary["by_modification"].items():
        color = color_for_percent(pct)
        print(f"  {mod:<{mod_width}} {color(f'{pct:>{pct_width - 1}.2f}%')}")

    quality = get_avalanche_quality(summary["avg_diff_percent"])
    verdict_color = color_for_percent(summary["avg_diff_percent"])
    suffix = f" (~{IDEAL_AVALANCHE_PERCENT}%)" if quality.level == "excellent" else ""
    print()
    print(f"  {labels['result']}: {verdict_color(quality.title + suffix)}")
    print()


def build_parser() -> argparse.ArgumentParser:
    messages = cli_config("messages")
    parser = argparse.ArgumentParser(
        prog=cli_config("prog"),
        description=cli_config("description"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=cli_config("epilog"),
    )
    parser.add_argument(
        "--text", "-t",
        required=True,
        help=messages["text_help"],
    )
    parser.add_argument(
        "--count", "-n",
        type=int,
        default=DEFAULT_EXPERIMENT_COUNT,
        help=(
            f"{messages['count_help']} "
            f"({messages['default_note']}: {DEFAULT_EXPERIMENT_COUNT})."
        ),
    )
    parser.add_argument(
        "--algo", "-a",
        choices=SUPPORTED_ALGORITHMS,
        default=DEFAULT_ALGORITHM,
        help=(
            f"{messages['algo_help']} "
            f"({messages['default_note']}: {DEFAULT_ALGORITHM})."
        ),
    )
    parser.add_argument(
        "--mod", "-m",
        choices=(*MODIFICATION_TYPES, ALL_MODIFICATIONS),
        default=ALL_MODIFICATIONS,
        help=(
            f"{messages['mod_help_prefix']}: "
            f"{', '.join(MODIFICATION_TYPES)} или {ALL_MODIFICATIONS} "
            f"({messages['default_note']}: {ALL_MODIFICATIONS})."
        ),
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help=messages["no_color_help"],
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help=messages["verbose_help"],
    )
    return parser


def execute_experiments(args: argparse.Namespace) -> list[AvalancheResult]:
    messages = cli_config("messages")
    modifications = (
        MODIFICATION_TYPES
        if args.mod == ALL_MODIFICATIONS
        else (args.mod,)
    )
    total = args.count * len(modifications)

    print(bold(f"  {messages['starting'].format(total=total)}\n"))

    pbar = None
    if tqdm is not None:
        pbar = tqdm(
            total=total,
            desc=cli_config("progress", "description"),
            unit=cli_config("progress", "unit"),
            ncols=PROGRESS_NCOLS,
            bar_format=cli_config("progress", "bar_format"),
        )

    completed = 0

    def show_result(result: AvalancheResult) -> None:
        nonlocal completed
        completed += 1
        if args.verbose:
            label = messages["experiment_label"].format(
                number=completed,
                modification_type=result.modification_type,
            )
            print_hash_pair(label, result, args.algo)
        if pbar is not None:
            pbar.update(1)

    def show_error(error: ValueError) -> None:
        message = messages["warning"].format(error=error)
        sys.stderr.write(f"\n  {message}\n")

    try:
        return run_experiments(
            args.text,
            count=args.count,
            algorithm=args.algo,
            modifications=modifications,
            result_callback=show_result,
            error_callback=show_error,
        )
    finally:
        if pbar is not None:
            pbar.close()


def main():
    global _use_color

    parser = build_parser()
    args = parser.parse_args()
    messages = cli_config("messages")
    _use_color = not args.no_color

    if args.count < MIN_EXPERIMENT_COUNT:
        parser.error(
            messages["count_error"].format(min_count=MIN_EXPERIMENT_COUNT)
        )

    print_banner()
    labels = cli_config("labels")
    original_hash = compute_hash(args.text, args.algo)
    print(f"  {labels['source_text']} : {yellow(repr(args.text))}")
    print(f"  {args.algo.upper()} {labels['hash']}      : {dim(original_hash)}")
    print()

    results = execute_experiments(args)
    print()

    if not results:
        print(red("  " + messages["no_results"]))
        sys.exit(1)

    if not args.verbose:
        print(bold("  " + messages["sample_result"]))
        result = results[-1]
        print_hash_pair(result.modification_type, result, args.algo)

    summary = summarize_results(results)
    print_summary_table(summary, args.algo)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  " + cli_config("messages", "interrupted"))
        sys.exit(0)
    except Exception as e:
        print(f"\n  {red(cli_config('messages', 'error'))} {e}")
        sys.exit(1)
