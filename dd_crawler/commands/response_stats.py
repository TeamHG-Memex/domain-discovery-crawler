import os.path
import glob
import re
from typing import Dict, List

from bokeh.charts import TimeSeries
from bokeh.models import Range1d
import bokeh.plotting
import pandas as pd
from scrapy.commands import ScrapyCommand
from scrapy.exceptions import UsageError

from dd_crawler.utils import get_domain


class Command(ScrapyCommand):
    requires_project = True

    def syntax(self):
        return '<files>'

    def add_options(self, parser):
        ScrapyCommand.add_options(self, parser)
        arg = parser.add_option
        arg('-o', '--output', help='prefix for charts (without ".html")')
        arg('--step', type=float, default=30, help='time step, s')
        arg('--smooth', type=int, default=50, help='smooth span')
        arg('--top', type=int, default=30, help='top domains to show')

    def short_desc(self):
        return 'Print short speed summary, save charts to a file'

    def run(self, args, opts):
        if not args:
            raise UsageError()
        if len(args) == 1 and '*' in args[0]:
            # paths were not expanded (docker)
            filenames = glob.glob(args[0])
        else:
            filenames = args
        del args
        filtered_filenames = [
            f for f in filenames
            if re.match(r'[a-z0-9]{12}\.csv$', os.path.basename(f))]
        filenames = filtered_filenames or filenames
        if not filenames:
            raise UsageError()

        response_logs = [
            pd.read_csv(
                filename,
                header=None,
                names=['timestamp', 'url', 'depth', 'priority', 'score',
                       'total_score', 'n_crawled', 'n_domains',
                       'n_relevant_domains'],
                index_col=False)
            for filename in filenames]
        print('Read data from {} files'.format(len(filenames)))

        all_rpms = [rpms for rpms in (
            get_rpms(name, rlog, step=opts.step, smooth=opts.smooth)
            for name, rlog in zip(filenames, response_logs))
                    if rpms is not None]
        if all_rpms:
            print_rpms(all_rpms, opts)

        print_scores(response_logs, opts)


def get_rpms(filename: str, response_log: pd.DataFrame,
             step: float, smooth: int) -> pd.DataFrame:
    timestamps = response_log['timestamp']
    buffer = []
    if len(timestamps) == 0:
        return
    get_t0 = lambda t: int(t / step) * step
    t0 = get_t0(timestamps[0])
    rpms = []
    for ts in timestamps:
        if get_t0(ts) != t0:
            rpms.append((t0, len(buffer) / (ts - buffer[0]) * 60))
            t0 = get_t0(ts)
            buffer = []
        buffer.append(ts)
    if rpms:
        name = os.path.basename(filename)
        rpms = pd.DataFrame(rpms, columns=['timestamp', name])
        if smooth:
            rpms[name] = rpms[name].ewm(span=smooth).mean()
        rpms.index = pd.to_datetime(rpms.pop('timestamp'), unit='s')
        return rpms


def print_rpms(all_rpms: List[pd.DataFrame], opts):
    joined_rpms = pd.DataFrame()
    for df in all_rpms:
        joined_rpms = joined_rpms.join(df, how='outer')
    joined_rpms.fillna(0, inplace=True)

    all_name = '<all>'
    col_names = [df.columns[0] for df in all_rpms]
    joined_rpms[all_name] = joined_rpms[col_names[0]]
    for col_name in col_names[1:]:
        joined_rpms[all_name] += joined_rpms[col_name]

    print_averages(joined_rpms, opts.step)
    rpms_title = 'Requests per minute'
    rpms_plot = TimeSeries(joined_rpms, plot_width=1000,
                           xlabel='time', ylabel='rpm', title=rpms_title)
    save_plot(rpms_plot, title=rpms_title, suffix='rpms', output=opts.output)


def save_plot(plot, title, suffix, output):
    if output:
        filename = '{}-{}.html'.format(output, suffix)
        print('Saving plot to {}'.format(filename))
        bokeh.plotting.output_file(filename, title=title, mode='inline')
        bokeh.plotting.save(plot)
    else:
        bokeh.plotting.show(plot)


def print_averages(items: Dict[str, pd.Series],
                   step: int, fmt: str = '{:.0f}'):
    last_n = 10
    print()
    print('{:<50}\t{:.0f} s\t{:.0f} m\t{}'.format(
        '', step, last_n * step / 60, 'All'))
    tpl = '{{:<50}}\t{fmt}\t{fmt}\t{fmt}'.format(fmt=fmt)
    for name, values in sorted(items.items()):
        print(tpl.format(
            name,
            values[-1:].mean(),
            values[-last_n:].mean(),
            values.mean()))
    print()


def print_scores(response_logs: List[pd.DataFrame], opts):
    joined = pd.concat(response_logs)  # type: pd.DataFrame
    binary_score = joined['score'] > 0.5
    print()
    print('Total number of pages: {}, relevant pages: {}, '
          'average binary score: {:.2f}, average score: {:.2f}'.format(
            len(joined), binary_score.sum(), binary_score.mean(),
            joined['score'].mean()))
    show_domain_stats(joined.copy(), output=opts.output, top=opts.top)
    joined.sort_values(by='timestamp', inplace=True)
    joined.index = pd.to_datetime(joined.pop('timestamp'), unit='s')
    if opts.smooth:
        crawl_time = (joined.index[-1] - joined.index[0]).total_seconds()
        avg_rps = len(joined) / crawl_time
        span = int(opts.smooth * opts.step * avg_rps)
        joined['score'] = joined['score'].ewm(span=span).mean()
    print_averages({'score': joined['score']}, opts.step, '{:.2f}')
    title = 'Page relevancy score'
    scores = joined['score'].resample('{}S'.format(opts.step)).mean()
    plot = TimeSeries(scores, plot_width=1000,
                      xlabel='time', ylabel='score', title=title)
    plot.set(y_range=Range1d(0, 1))
    save_plot(plot, title=title, suffix='score', output=opts.output)


def show_domain_stats(log, output, top=50):
    log['Domain'] = log['url'].apply(get_domain)
    by_domain = log.groupby('Domain')
    top_domains = (
        by_domain.count().sort_values('url', ascending=False)['url'].index)
    stats_by_domain = pd.DataFrame(index=top_domains)
    stats_by_domain['Pages'] = by_domain.count()['url']
    stats_by_domain['Total Score'] = by_domain.sum()['score']
    stats_by_domain['Mean Score'] = by_domain.mean()['score']
    stats_by_domain['Max Depth'] = by_domain.max()['depth']
    stats_by_domain['Median Depth'] = by_domain.median()['depth'].astype(int)
    print()
    pages = stats_by_domain['Pages']
    print('Top {} domains stats (covering {:.1%} pages)'
          .format(top, pages[:top].sum() / pages.sum()))
    print(stats_by_domain[:top])
    if output:
        filename = '{}-by-domain.csv'.format(output)
        stats_by_domain.to_csv(filename)
        print()
        print('Saved domain stats to {}'.format(filename))
