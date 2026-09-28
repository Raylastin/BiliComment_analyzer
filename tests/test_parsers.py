from __future__ import annotations

from bili_analyzer.services.crawler.parsers import (
    parse_comment,
    parse_video_info,
)


def test_parse_video_info():
    data = {
        "bvid": "BV1xx411c7mD",
        "aid": 170001,
        "title": "示例视频",
        "tags": ["测试", "情感"],
        "pubdate": 1700000000,
        "stat": {"view": 12345, "like": 678, "reply": 20},
        "owner": {"mid": 9001, "name": "UP主"},
    }
    result = parse_video_info(data)
    assert result["bvid"] == "BV1xx411c7mD"
    assert result["aid"] == 170001
    assert result["play_count"] == 12345
    assert result["tags"] == ["测试", "情感"]
    assert result["pubdate"] is not None


def test_parse_main_comment_and_reply():
    main = {
        "rpid": 1001,
        "mid": 101,
        "member": {
            "mid": 101,
            "uname": "用户A",
            "avatar": "http://avatar/a",
            "vip": {"vipStatus": 1, "vipType": 2},
        },
        "content": {"message": "很好"},
        "ctime": 1700000001,
        "like": 5,
        "rcount": 2,
    }
    main_parsed = parse_comment(main, is_reply=False)
    assert main_parsed["rpid"] == 1001
    assert main_parsed["parent_rpid"] is None
    assert main_parsed["root_rpid"] is None
    assert main_parsed["user"]["vip_status"] == 1

    reply = {
        "rpid": 2001,
        "mid": 103,
        "member": {"mid": 103, "uname": "用户C"},
        "content": {"message": "回复"},
        "ctime": 1700000002,
        "like": 1,
        "parent": 1001,
        "root": 1001,
    }
    reply_parsed = parse_comment(reply, is_reply=True)
    assert reply_parsed["parent_rpid"] == 1001
    assert reply_parsed["root_rpid"] == 1001
    assert reply_parsed["is_reply"] is True

