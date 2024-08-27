from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import re
from StrUtil import StrUtil

class WidgetUtil:
    FEATURE_KEYS = ['class', 'resource-id', 'text', 'content-desc', 'clickable', 'password', 'naf']
    WIDGET_CLASSES = ['android.widget.EditText', 'android.widget.MultiAutoCompleteTextView', 'android.widget.TextView',
                      'android.widget.Button', 'android.widget.ImageButton', 'android.view.View']
    state_to_widgets = {}  # for a gui state, there are "all_widgets": a list of all widgets, and
                           # "most_similar_widgets": a dict for a source widget and the list of its most similar widgets and scores

    def __init__(self):
        pass  # 如果有需要，可以在这里进行初始化操作

    @staticmethod
    def get_gui_signature(xml_dom, pkg_name, act_name):
        """Get the signature for a GUI state by the package/activity name and the xml hierarchy
        Breadth first traversal for the non-leaf/leaf nodes and their cumulative index sequences
        """
        xml_dom = re.sub(r'&#\d+;', "", xml_dom)  # remove emoji
        root = ET.fromstring(xml_dom)
        queue = [(root, '0')]
        layouts = []
        executable_leaves = []
        while queue:
            node, idx = queue.pop()
            if len(list(node)):  # the node has child(ren)
                layouts.append(idx)
                for i, child in enumerate(node):
                    queue.insert(0, (child, idx + '-' + str(i)))
            else:  # a leaf node
                executable_leaves.append(idx)
        sign = [pkg_name, act_name, '+'.join(layouts), '+'.join(executable_leaves)]
        return '!'.join(sign)

    @classmethod
    def get_widget_signature(cls, w):
        """Get the signature for a GUI widget by its attributes"""
        sign = []
        for k in cls.FEATURE_KEYS + ['package', 'activity']:
            if k in w:
                sign.append(w[k])
            else:
                sign.append('')
        return '!'.join(sign)

    @classmethod
    def get_most_similar_widget_from_cache(cls, gui_signature, widget_signature):
        """Return the most similar widget and the score to the source widget in a gui state in cache"""
        if gui_signature not in cls.state_to_widgets:
            return None, -1
        if 'most_similar_widgets' in cls.state_to_widgets[gui_signature]:
            if widget_signature in cls.state_to_widgets[gui_signature]['most_similar_widgets']:
                return cls.state_to_widgets[gui_signature]['most_similar_widgets'][widget_signature][0]
        return None, -1

    @classmethod
    def get_all_widgets_from_cache(cls, gui_signature):
        """Return all widgets in a gui state in cache"""
        if gui_signature in cls.state_to_widgets and 'all_widgets' in cls.state_to_widgets[gui_signature]:
            return cls.state_to_widgets[gui_signature]['all_widgets']
        else:
            return None

    @staticmethod
    def get_parent_text(soup_ele):
        parent_text = ''
        parent = soup_ele.find_parent()
        if parent and 'text' in parent.attrs and parent['text']:
            parent_text += parent['text']
        parent = parent.find_parent()
        if parent and 'text' in parent.attrs and parent['text'] and parent['class'][0] == 'TextInputLayout':
            parent_text += parent['text']
        return parent_text

    @staticmethod
    def get_sibling_text(soup_ele):
        sibling_text = ''
        parent = soup_ele.find_parent()
        if parent and parent['class'][0] in ['android.widget.LinearLayout', 'android.widget.RelativeLayout']:
            prev_sib = soup_ele.previous_sibling
            if prev_sib and 'text' in prev_sib.attrs and prev_sib['text']:
                sibling_text = prev_sib['text']
        return sibling_text

    @classmethod
    def get_attrs(cls, dom, attr_name, attr_value, tag_name=''):
        soup = BeautifulSoup(dom, 'lxml-xml')
        if attr_name == 'text-contain':
            cond = {'text': lambda x: x and attr_value in x}
        else:
            cond = {attr_name: attr_value}
        if tag_name:
            cond['class'] = tag_name
        ele = soup.find(attrs=cond)
        d = {}
        for key in cls.FEATURE_KEYS:
            d[key] = ele.attrs[key] if key in ele.attrs else ""
            if key == 'class':
                d[key] = d[key][0]  # 只考虑第一个class
            elif key == 'clickable' and key in ele.attrs and ele.attrs[key] == 'false':
                d[key] = WidgetUtil.propagate_clickable(ele)

        # 新增：获取parent_text和sibling_text
        d['parent_text'] = WidgetUtil.get_parent_text(ele)
        d['sibling_text'] = WidgetUtil.get_sibling_text(ele)

        # 新增：获取filename
        d['filename'] = WidgetUtil.get_filename(ele)

        # 新增：获取atm_neighbor
        d['atm_neighbor'] = WidgetUtil.atm_neighbor(ele, soup.find_all())  # 需要所有widgets的上下文

        return d

    @classmethod
    def get_empty_attrs(cls):
        d = {}
        for key in cls.FEATURE_KEYS:
            d[key] = ""
        d['parent_text'] = ""
        d['sibling_text'] = ""
        return d

    @classmethod
    def find_all_widgets(cls, dom, pkg, act, target_pkg, update_cache=True):
        if 'com.android.launcher' in pkg:
            return []

        if pkg != target_pkg:
            return []

        if act.startswith('com.facebook'):
            return []

        gui_signature = WidgetUtil.get_gui_signature(dom, pkg, act)
        if not update_cache:
            widgets = WidgetUtil.get_all_widgets_from_cache(gui_signature)
            if widgets:
                return widgets

        soup = BeautifulSoup(dom, 'lxml-xml')
        widgets = []
        all_widgets = soup.find_all()  # 或者找到所有你需要的元素

        for w_class in cls.WIDGET_CLASSES:
            elements = soup.find_all(attrs={'class': w_class})
            for e in elements:
                d = cls.get_widget_from_soup_element(e, all_widgets)
                if d:
                    if 'yelp' in gui_signature and 'text' in d and d['text'] == 'Sign up with Google':
                        d['text'] = 'SIGN UP WITH GOOGLE'  # Specific for Yelp
                    d['package'], d['activity'] = pkg, act
                    widgets.append(d)

        if widgets or update_cache:
            cls.state_to_widgets[gui_signature] = {'all_widgets': widgets, 'most_similar_widgets': {}}
        return widgets

    @classmethod
    def get_widget_from_soup_element(cls, e, all_widgets):
        if not e:
            return None
        d = {}
        if 'enabled' in e.attrs and e['enabled'] == 'true':
            for key in cls.FEATURE_KEYS:
                d[key] = e.attrs[key] if key in e.attrs else ''
                if key == 'class':
                    d[key] = d[key].split()[0]
                elif key == 'clickable' and key in e.attrs and e.attrs[key] == 'false':
                    d[key] = WidgetUtil.propagate_clickable(e)
                elif key == 'resource-id':
                    rid = d[key].split('/')[-1]
                    prefix = ''.join(d[key].split('/')[:-1])
                    d[key] = rid
                    d['id-prefix'] = prefix + '/' if prefix else ''

            d['parent_text'] = WidgetUtil.get_parent_text(e)
            d['sibling_text'] = WidgetUtil.get_sibling_text(e)
            d['filename'] = WidgetUtil.get_filename(e)

            # 使用已经传递的 all_widgets 来计算邻居
            d['atm_neighbor'] = WidgetUtil.atm_neighbor(d, all_widgets)

            return d
        else:
            return None

    @staticmethod
    def get_filename(soup_ele):
        filename = ''
        if 'filename' in soup_ele.attrs:
            filename = soup_ele.attrs['filename']
        else:
            if 'src' in soup_ele.attrs:
                filename = soup_ele.attrs['src'].split('/')[-1]
            elif 'href' in soup_ele.attrs:
                filename = soup_ele.attrs['href'].split('/')[-1]
        return filename


    @staticmethod
    def atm_neighbor(new_widget, all_widgets):
        """
        计算指定 widget 的 ATM neighbor。
        """
        neighbors = []
        for widget in all_widgets:
            if WidgetUtil.is_neighbor(new_widget, widget):
                neighbors.append(widget)
        return neighbors

    @staticmethod
    def is_neighbor(widget1, widget2):
        """
        判断两个 widget 是否是邻居。
        假设两个 widget 的 class 相同且 resource-id 不同即认为是邻居。
        """
        if widget1.get('class') == widget2.get('class') and widget1.get('resource-id') != widget2.get('resource-id'):
            return True
        return False

    @classmethod
    def propagate_clickable(cls, soup_element):
        parent = soup_element.find_parent()
        if 'clickable' in parent.attrs and parent['clickable'] == 'true':
            return 'true'
        for i in range(2):
            parent = parent.find_parent()
            if parent and 'class' in parent.attrs and parent['class'][0] in ['android.widget.ListView']:
                if 'clickable' in parent.attrs and parent['clickable'] == 'true':
                    return 'true'
        return 'false'

    @staticmethod
    def weighted_sim(new_widget, old_widget, use_stopwords=True, cross_check=False):
        # 包含新的属性在计算相似度时使用
        attrs = ['resource-id', 'text', 'content-desc', 'parent_text', 'sibling_text', 'filename', 'atm_neighbor']

        is_attr_existed_old = [a in old_widget and old_widget[a] for a in attrs]
        is_attr_existed_new = [a in new_widget and new_widget[a] for a in attrs]
        if not any(is_attr_existed_old) or not any(is_attr_existed_new):
            return None

        w_scores = []
        for attr in attrs:
            if attr in new_widget and attr in old_widget:
                sim = StrUtil.w2v_sent_sim(new_widget[attr], old_widget[attr])  # 使用自定义的相似度函数
                if sim is not None:
                    w_scores.append(sim)

        if w_scores:
            return sum(w_scores) / len(w_scores)  # 返回平均相似度
        else:
            return None

    @classmethod
    def is_equal(cls, w1, w2, ignore_activity=False):
        if not w1 or not w2:
            return False
        keys_for_equality = set(cls.FEATURE_KEYS)
        keys_for_equality.remove('naf')
        if not ignore_activity:
            keys_for_equality = keys_for_equality.union({'package', 'activity'})
        for k in keys_for_equality:
            if (k in w1 and k not in w2) or (k not in w1 and k in w2):
                return False
            if k in w1 and k in w2:
                v1, v2 = w1[k], w2[k]
                if k == 'resource-id' and 'id-prefix' in w1:
                    v1 = w1['id-prefix'] + w1[k]
                if k == 'resource-id' and 'id-prefix' in w2:
                    v2 = w2['id-prefix'] + w2[k]
                if v1 != v2:
                    return False
        return True

    @classmethod
    def locate_widget(cls, dom, criteria):
        regex_cria = {}
        for k, v in criteria.items():
            if v:
                v = v.replace('+', r'\+')  # for error when match special char '+'
                v = v.replace('?', r'\?')  # for error when match special char '?'
                if k == 'resource-id':
                    regex_cria[k] = re.compile(f'{v}$')
                else:
                    regex_cria[k] = re.compile(f'{v}')
        if not regex_cria:
            return None
        soup = BeautifulSoup(dom, 'lxml-xml')

        # 获取所有widgets
        all_widgets = soup.find_all()  # 假设你需要获取所有的元素

        # 查找符合条件的widget并传递所有widgets
        return cls.get_widget_from_soup_element(soup.find(attrs=regex_cria), all_widgets)

    @classmethod
    def most_similar(cls, src_event, widgets, use_stopwords=True, expand_btn_to_text=False, cross_check=False):
        src_class = src_event['class']
        is_clickable = src_event['clickable']
        is_password = src_event['password']
        similars = []
        tgt_classes = [src_class]
        if src_class in ['android.widget.ImageButton', 'android.widget.Button']:
            tgt_classes = ['android.widget.ImageButton', 'android.widget.Button']
            if expand_btn_to_text:
                tgt_classes.append('android.widget.TextView')
        elif src_class == 'android.widget.TextView':
            if is_clickable == 'true':
                tgt_classes += ['android.widget.ImageButton', 'android.widget.Button']
                if re.search(r'https://\w+\.\w+', src_event['text']):
                    tgt_classes.append('android.widget.EditText')
            elif src_event['action'][0].startswith('wait_until_text_presence'):
                tgt_classes.append('android.widget.EditText')
        elif src_class == 'android.widget.EditText':
            tgt_classes.append('android.widget.MultiAutoCompleteTextView')
            if src_event['action'][0].startswith('wait_until_text_presence'):
                tgt_classes.append('android.widget.TextView')
            elif re.search(r'https://\w+\.\w+', src_event['text']):
                tgt_classes.append('android.widget.TextView')
        elif src_class == 'android.widget.MultiAutoCompleteTextView':
            tgt_classes.append('android.widget.EditText')

        for w in widgets:
            need_evaluate = False
            if w['class'] in tgt_classes:
                if 'password' in w and w['password'] != is_password:
                    continue
                if 'clickable' in w:
                    if w['clickable'] == is_clickable:
                        need_evaluate = True
                    elif 'action' in src_event and 'class' in w:
                        if src_event['action'][0].startswith('wait_until') \
                                and w['class'] in ['android.widget.EditText', 'android.widget.TextView']:
                            need_evaluate = True
                        elif src_event['action'][0].startswith('swipe') and w['class'] in ['android.widget.TextView']:
                            need_evaluate = True
                else:
                    need_evaluate = True
            score = WidgetUtil.weighted_sim(w, src_event, use_stopwords, cross_check) if need_evaluate else None
            if score:
                similars.append((w, score))
        similars.sort(key=lambda x: x[1], reverse=True)
        return similars

    @classmethod
    def get_nearest_button(cls, dom, w):
        soup = BeautifulSoup(dom, 'lxml-xml')
        for btn_class in ['android.widget.ImageButton', 'android.widget.Button', 'android.widget.EditText']:
            all_btns = soup.find_all(attrs={'class': btn_class})
            if all_btns and len(all_btns) > 0:
                return cls.get_widget_from_soup_element(all_btns[0])
        return None
