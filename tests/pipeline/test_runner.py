from __future__ import annotations

from unittest.mock import MagicMock, patch

# Import runner at module level so patches applied inside tests correctly
# replace names in the already-imported module's namespace.
# (Importing inside a `with patch(...)` block would overwrite the patches
# when the module's top-level imports execute.)
from src.pipeline import runner


def _make_mock_video(video_id: str = "vid1") -> MagicMock:
    v = MagicMock()
    v.video_id = video_id
    v.url = f"https://youtube.com/watch?v={video_id}"
    v.title = f"Test Video {video_id}"
    return v


def test_run_processes_all_videos():
    videos = [_make_mock_video("vid1"), _make_mock_video("vid2")]

    with patch("src.pipeline.runner.init_db"), \
         patch("src.pipeline.runner.poll_channels", return_value=videos), \
         patch("src.pipeline.runner._process_video") as mock_process, \
         patch("src.pipeline.runner.stop_self"):
        runner.run()

    assert mock_process.call_count == 2
    mock_process.assert_any_call(videos[0])
    mock_process.assert_any_call(videos[1])


def test_run_shuts_down_when_no_videos():
    with patch("src.pipeline.runner.init_db"), \
         patch("src.pipeline.runner.poll_channels", return_value=[]), \
         patch("src.pipeline.runner.stop_self") as mock_shutdown:
        runner.run()

    mock_shutdown.assert_called_once()


def test_run_shuts_down_even_when_video_fails():
    videos = [_make_mock_video("vid_fail")]

    with patch("src.pipeline.runner.init_db"), \
         patch("src.pipeline.runner.poll_channels", return_value=videos), \
         patch("src.pipeline.runner._process_video", side_effect=RuntimeError("boom")), \
         patch("src.pipeline.runner.log_event"), \
         patch("src.pipeline.runner.stop_self") as mock_shutdown:
        runner.run()  # must not raise

    mock_shutdown.assert_called_once()


def test_run_continues_after_one_video_fails():
    vid1 = _make_mock_video("vid1")
    vid2 = _make_mock_video("vid2")
    results = []

    def fake_process(video):
        if video.video_id == "vid1":
            raise RuntimeError("vid1 exploded")
        results.append(video.video_id)

    with patch("src.pipeline.runner.init_db"), \
         patch("src.pipeline.runner.poll_channels", return_value=[vid1, vid2]), \
         patch("src.pipeline.runner._process_video", side_effect=fake_process), \
         patch("src.pipeline.runner.log_event"), \
         patch("src.pipeline.runner.stop_self"):
        runner.run()

    assert results == ["vid2"]
