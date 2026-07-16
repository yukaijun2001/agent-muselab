from backend.session_title_llm import _clean_title


def test_clean_title_removes_wrappers_and_prefix():
    assert _clean_title('标题："MuseLab中转站协议适配。"') == "MuseLab中转站协议适配"


def test_clean_title_limits_length():
    assert len(_clean_title("这是一个特别特别特别特别特别特别长的会话标题需要截断")) <= 24


def test_replace_auto_title_does_not_overwrite_manual_rename(app_module):
    from backend import sessions as sess
    meta = sess.create_session()
    sess.bump_session(meta["id"], auto_rename_from="原始问题")
    fallback = sess.get_session_meta(meta["id"])["name"]
    assert sess.replace_auto_title(meta["id"], fallback, "生成后的主题") is True
    sess.rename_session(meta["id"], "用户手动名称")
    assert sess.replace_auto_title(meta["id"], "生成后的主题", "迟到的标题") is False
    assert sess.get_session_meta(meta["id"])["name"] == "用户手动名称"
