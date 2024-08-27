import json
import os
from copy import deepcopy
from bs4 import BeautifulSoup
from bs4.element import Tag  # 正确导入Tag类

# from numpy import dot
# from numpy.linalg import norm

from const import TEST_REPO
from Databank import Databank
import imaplib


class Util:

    @staticmethod
    def compose(attrs, tid, actions, pkg_name, act_name, event_type):
        attrs['tid'] = tid
        # attrs['order'] = order
        attrs['package'] = pkg_name
        attrs['activity'] = act_name
        attrs['ignorable'] = 'false'
        attrs['event_type'] = event_type  # 'gui', 'oracle', 'stepping'
        # if the action is wait_until_presence, adjust the content-desc for current app instead of that of the target app
        # e.g., ['wait_until_element_presence', 10, 'xpath', '//*[@content-desc="Open Menu"]']
        if actions[0] == 'wait_until_element_presence' and actions[2] == 'xpath' and '@content-desc=' in actions[3]:
            pre, post = actions[3].split('@content-desc=')
            post = f'@content-desc="{attrs["content-desc"]}"' + ''.join(post.split('"')[2:])
            actions[3] = pre + post
        attrs['action'] = actions
        return attrs

    @staticmethod
    def save_events(events, config_id):
        # 定义一个转换函数来处理不可序列化的对象
        def convert_to_serializable(obj):
            if isinstance(obj, Tag):  # 使用导入的Tag类
                return str(obj)  # 将 BeautifulSoup Tag 对象转换为字符串
            elif isinstance(obj, list):
                return [convert_to_serializable(item) for item in obj]
            elif isinstance(obj, dict):
                return {key: convert_to_serializable(value) for key, value in obj.items()}
            else:
                return obj

        # 转换所有事件为可序列化的格式
        serializable_events = convert_to_serializable(events)

        # 检查 'output/' 目录是否存在，如果不存在，则创建它
        output_dir = 'output'
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # 继续现有的保存逻辑
        with open(f'{output_dir}/{config_id}.json', 'w') as f:
            json.dump(serializable_events, f, indent=2)

    @staticmethod
    def save_aug_events(actions, fpath):
        with open(fpath, 'w') as f:
            json.dump(actions, f, indent=2)

    @staticmethod
    def load_events(config_id, target):
        # target: 'generated', 'base_from', 'base_to'
        # e.g., a41a-a42a-b41 -> [Util.TEST_REPO, 'a4', 'b41', 'base', 'a41a.json']
        fpath = [TEST_REPO, config_id[:2], config_id.split('-')[-1]]
        sub_dir = ''
        if target == 'generated':
            fpath += ['generated', sub_dir, config_id + '.json']
        elif target == '0-step':
            fpath += ['generated', '0-step', sub_dir, config_id + '.json']
        elif target == '1-step':
            fpath += ['generated', '1-step', sub_dir, config_id + '.json']
        elif target == '2-step':
            fpath += ['generated', '2-step', sub_dir, config_id + '.json']
        elif target == 'base_from':
            fpath += ['base', config_id.split('-')[0] + '.json']
        elif target == 'base_to':
            fpath += ['base', config_id.split('-')[1] + '.json']
        else:
            assert False, "Wrong target"
        fpath = os.path.join(*fpath)
        assert os.path.exists(fpath), f"Invalid file path: {fpath}"
        act_list = []
        with open(fpath, 'r', encoding='utf-8') as f:
            acts = json.load(f)
        for act in acts:
            act_list.append(act)
        return act_list

    @staticmethod
    def delete_emails():
        dbank = Databank()
        try:
            print("Deleting all testing messages in the inbox")
            m = imaplib.IMAP4_SSL("imap.gmail.com")
            m.login(dbank.get_login_email(), dbank.get_gmail_password())
            m.select("inbox")
            result, data = m.uid('search', None, rf'X-GM-RAW "subject:\"{dbank.get_email_subject()}\""')
            if data:
                for uid in data[0].split():
                    m.uid('store', uid, '+X-GM-LABELS', '\\Trash')
            # empty trash
            m.select('[Gmail]/Trash')  # select all trash
            m.store("1:*", '+FLAGS', '\\Deleted')  # Flag all Trash as Deleted
            m.expunge()
            m.close()
            m.logout()
        except:
            print("Error when deleting testing messages.")

    # def cosine_sim(v1, v2):
    #     return dot(v1, v2) / (norm(v1) * norm(v2))
    #
    #
    # def get_layout_vec(vec):
    #     denominator = sum(vec)
    #     if denominator > 0:
    #         return [v/denominator for v in vec]
    #     else:
    #         return [v for v in vec]
