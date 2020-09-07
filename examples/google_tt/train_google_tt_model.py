"""
@Description: Sampling-Bias-Corrected Neural Model Training Demo
@version: 
@License: MIT
@Author: Wang Yao
@Date: 2020-09-03 16:26:18
@LastEditors: Wang Yao
@LastEditTime: 2020-09-07 15:22:58
"""
import os
import sys
sys.path.append('../..')
import math
from src.embedding.google_tt.modeling import build_model
from src.embedding.google_tt.train import get_dataset_from_csv_files
from src.embedding.google_tt.train import train_model



if __name__ == "__main__":
    left_columns = [
        'past_watches',
        'seed_id',
        'seed_category',
        'seed_tags',
        'seed_gap_time',
        'seed_duration_time',
        'seed_play_count',
        'seed_like_count',
        'seed_share_count',
        'seed_collect_count',
        # 'seed_reply_count'
    ]
    right_columns = [
        'cand_id',
        'cand_category',
        'cand_tags',
        'cand_gap_time',
        'cand_duration_time',
        'cand_play_count',
        'cand_like_count',
        'cand_share_count',
        'cand_collect_count',
        # 'cand_reply_count'
    ]
    csv_header = [
        'label',
        'udid',
        'past_watches',
        'seed_id',
        'seed_category',
        'seed_tags',
        'seed_gap_time',
        'seed_duration_time',
        'seed_play_count',
        'seed_like_count',
        'seed_share_count',
        'seed_collect_count',
        # 'seed_reply_count',
        'cand_id',
        'cand_category',
        'cand_tags',
        'cand_gap_time',
        'cand_duration_time',
        'cand_play_count',
        'cand_like_count',
        'cand_share_count',
        'cand_collect_count',
        # 'cand_reply_count'
    ]
    
    def _get_steps(fns, batch_size, skip_header=True):
        _total_num = 0
        for fn in fns:
            cmd = "wc -l < {}".format(fn)
            cmd_res = os.popen(cmd)
            _num_lines = int(cmd_res.read().strip())
            if skip_header is True:
                _num_lines -= 1
            _total_num += _num_lines
        _steps = math.ceil(_total_num / batch_size)
        return _steps

    filenames = [
        '/home/xddz/data/two_tower_data/2020-09-01.csv',
        '/home/xddz/data/two_tower_data/2020-09-02.csv',
        '/home/xddz/data/two_tower_data/2020-09-03.csv'
    ]
    batch_size = 512
    epochs = 10
    steps = _get_steps(filenames, batch_size)

    print(steps)

    train_dataset = get_dataset_from_csv_files(
        filenames, 
        left_columns, 
        right_columns,
        csv_header, 
        batch_size=batch_size
    )

    left_model, right_model = build_model()
    
    print(left_model.get_weights()[0])
    print(right_model.get_weights()[0])

    left_model, right_model = train_model(
        left_model, 
        right_model, 
        train_dataset, 
        steps,
        epochs=epochs,
        ids_column='cand_id',
        ids_hash_bucket_size=100000
    )

    print(left_model.get_weights()[0])
    print(right_model.get_weights()[0])

