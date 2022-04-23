#
# Copyright Cloudlab URV 2020
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import os
import pylab
import logging
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.collections import LineCollection

pylab.switch_backend("Agg")
logger = logging.getLogger(__name__)

READ_COLOR = (0.12156862745098039, 0.4666666666666667, 0.7058823529411765)
WRITE_COLOR = (1.0, 0.4980392156862745, 0.054901960784313725)


def create_agg_bdwth_plot(res_write, res_read, dst):

    def compute_times_rates(start_time, d):

        x = np.array(d)
        tzero = start_time
        tr_start_time = x[:, 0] - tzero
        tr_end_time = x[:, 1] - tzero
        rate = x[:, 2]

        N = len(tr_start_time)
        runtime_rate_hist = np.zeros((N, len(runtime_bins)))

        for i in range(N):
            s = tr_start_time[i]
            e = tr_end_time[i]
            a, b = np.searchsorted(runtime_bins, [s, e])
            if b-a > 0:
                runtime_rate_hist[i, a:b] = rate[i]

        return {'start_time': tr_start_time,
                'end_time': tr_end_time,
                'rate': rate,
                'runtime_rate_hist': runtime_rate_hist}

    fig = pylab.figure(figsize=(5, 5))
    ax = fig.add_subplot(1, 1, 1)
    for datum, l, c in [(res_write, 'Aggregate Write Bandwidth', WRITE_COLOR), (res_read, 'Aggregate Read Bandwidth', READ_COLOR)]:
        start_time = datum['start_time']
        mb_rates = [(res['start_time'], res['end_time'], res['mb_rate']) for res in datum['results']]
        max_seconds = int(max([mr[1]-start_time for mr in mb_rates])*1.2)
        max_seconds = 8 * round(max_seconds/8)
        runtime_bins = np.linspace(0, max_seconds, max_seconds)

        mb_rates_hist = compute_times_rates(start_time, mb_rates)
        gb_rates = mb_rates_hist['runtime_rate_hist'].sum(axis=0)/1000
        ax.plot(gb_rates, label=l, c=c)
        with open('./bandwidth.txt', 'a+') as f:
            f.write(l + ':' + str(max(gb_rates)) + '\n')


    ax.set_xlabel('Execution Time (sec)')
    ax.set_ylabel("GB/sec")
    ax.set_xlim(0, )
    ax.set_ylim(0, )
    pylab.legend()
    pylab.grid(True, axis='y')

    dst = os.path.expanduser(dst) if '~' in dst else dst

    fig.tight_layout()
    fig.savefig(dst)
