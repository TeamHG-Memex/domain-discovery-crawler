import os.path
import glob
from typing import Dict, List

from bokeh.charts import TimeSeries
import bokeh.plotting
import pandas
from scrapy.commands import ScrapyCommand
from scrapy.exceptions import UsageError


class Command(ScrapyCommand):
    requires_project = True

    def syntax(self):
        return '<files>'

    def add_options(self, parser):
        ScrapyCommand.add_options(self, parser)
        parser.add_option('-o', '--output',
                          help='base name for charts (without html)')
        parser.add_option('--step', type=float, default=30, help='time step, s')
        parser.add_option('--smooth', type=int, help='smooth span')

    def short_desc(self):
        return 'Print short speed summary, save charts to a file'

    def run(self, args, opts):
        if not args:
            raise UsageError()
        if len(args) == 1 and '*' in args[0]:
            # paths were not expanded (docker)
            args = glob.glob(args[0])
        if not args:
            raise UsageError()

        response_logs = [
            pandas.read_csv(filename, header=None, names=[
                'timestamp', 'url', 'depth', 'priority', 'score'])
            for filename in args]

        all_rpms = [rpms for rpms in (
            get_rpms(name, rlog, step=opts.step, smooth=opts.smooth)
            for name, rlog in zip(args, response_logs))
                    if rpms is not None]
        if all_rpms:
            print_rpms(all_rpms, opts)

        print_scores(response_logs, opts)


def get_rpms(filename: str, response_log: pandas.DataFrame,
             step: float, smooth: int) -> pandas.DataFrame:
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
        rpms = pandas.DataFrame(rpms, columns=['timestamp', name])
        rpms.fillna(0, inplace=True)  # FIXME - this does not really work
        if smooth:
            rpms[name] = rpms[name].ewm(span=smooth).mean()
        rpms.index = pandas.to_datetime(rpms.pop('timestamp'), unit='s')
        return rpms


def print_rpms(all_rpms: List[pandas.DataFrame], opts):
    joined_rpms = all_rpms[0]
    all_name = '<all>'
    joined_rpms[all_name] = all_rpms[0][all_rpms[0].columns[0]]
    for df in all_rpms[1:]:
        joined_rpms = joined_rpms.join(df, how='outer')
        joined_rpms[all_name] += df[df.columns[0]]
    print_averages(joined_rpms, opts.step)
    rpms_title = 'Requests per minute'
    rpms_plot = TimeSeries(joined_rpms, plot_width=1000,
                           xlabel='time', ylabel='rpm', title=rpms_title)
    save_plot(rpms_plot, title=rpms_title, suffix='rpms', output=opts.output)


def save_plot(plot, title, suffix, output):
    if output:
        rpms_output = '{}-{}.html'.format(output, suffix)
        print('Saving plot to {}'.format(rpms_output))
        bokeh.plotting.output_file(rpms_output, title=title, mode='inline')
        bokeh.plotting.save(plot)
    else:
        bokeh.plotting.show(plot)


def print_averages(items: Dict[str, pandas.Series],
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


def print_scores(response_logs: List[pandas.DataFrame], opts):
    joined = pandas.DataFrame()
    for df in response_logs:
        df.index = df.pop('url')
        joined = joined.join(df, how='outer')
    binary_score = joined['score'] > 0.5
    print()
    print('Total number of pages: {}, relevant pages: {}, '
          'average binary score: {:.2f}, average score: {:.2f}'.format(
            len(joined), binary_score.sum(), binary_score.mean(),
            joined['score'].mean()))
    joined.sort_values(by='timestamp', inplace=True)
    joined.index = pandas.to_datetime(joined.pop('timestamp'), unit='s')
    if opts.smooth:
        span = opts.smooth * opts.step
        joined['score'] = (joined['score'] > 0.5).ewm(span=span).mean()
    print_averages({'score': joined['score']}, opts.step, '{:.2f}')
    title = 'Page relevancy score'
    plot = TimeSeries(joined['score'], plot_width=1000,
                      xlabel='time', ylabel='score', title=title)
    save_plot(plot, title=title, suffix='score', output=opts.output)
