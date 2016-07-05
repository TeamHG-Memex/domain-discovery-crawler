import os.path
import glob

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
        parser.add_option('-o', '--output', help='html file for charts')
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

        all_rpms = [rpms for rpms in (
            get_rpms(f, step=opts.step, smooth=opts.smooth) for f in args)
                    if rpms is not None]
        if not all_rpms:
            return
        joined_rpms = all_rpms[0]
        joined_rpms['all'] = all_rpms[0][all_rpms[0].columns[0]]
        for df in all_rpms[1:]:
            joined_rpms = joined_rpms.join(df, how='outer')
            joined_rpms['all'] += df[df.columns[0]]

        last_n = 10
        print()
        print('{:<50}\t{:.0f} s\t{:.0f} m\t{}'.format(
            'Name', opts.step, last_n * opts.step / 60, 'All'))
        for name, values in sorted(joined_rpms.items()):
            print('{:<50}\t{:.0f}\t{:.0f}\t{:.0f}'.format(
                name,
                values[-1:].mean(),
                values[-last_n:].mean(),
                values.mean()))
        print()

        title = 'Requests per minute'
        plot = TimeSeries(joined_rpms, plot_width=1000,
                          xlabel='time', ylabel='rpm', title=title)
        if opts.output:
            print('Saving plot to {}'.format(opts.output))
            bokeh.plotting.output_file(opts.output, title=title, mode='inline')
            bokeh.plotting.save(plot)
        else:
            bokeh.plotting.show(plot)


def get_rpms(filename: str, step: float, smooth: int) -> pandas.DataFrame:
    response_log = pandas.read_csv(
        filename, header=None, names=['timestamp', 'url'])
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
