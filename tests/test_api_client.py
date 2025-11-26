import os
import sys
import unittest
from io import BytesIO
from unittest.mock import patch, MagicMock

import gradio as gr
from PIL import Image

# 将项目根目录添加到 Python 路径中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import api_client


# 修正：模拟 i18n.get 函数，使其签名与真实函数匹配
def mock_i18n_get(key, default=None, **kwargs):
    if kwargs:
        return f"{key}{kwargs}"
    return key

@patch('api_client.i18n.get', side_effect=mock_i18n_get)
class TestApiClient(unittest.TestCase):

    def setUp(self):
        """初始化一些通用的测试数据"""
        self.api_key = "fake_api_key"
        self.prompt = "A cat sitting on a mat"
        buffer = BytesIO()
        Image.new('RGB', (100, 100), color = 'red').save(buffer, 'PNG')
        self.fake_image_bytes = buffer.getvalue()

    @patch('api_client.genai.Client')
    def test_call_google_genai_success(self, MockGenaiClient, mock_get):
        """测试 API 调用成功并返回图像的场景"""
        mock_response = MagicMock()
        mock_part = MagicMock()
        mock_part.inline_data.data = self.fake_image_bytes
        mock_response.parts = [mock_part]
        mock_client_instance = MockGenaiClient.return_value
        mock_client_instance.models.generate_content.return_value = mock_response

        result_image = api_client.call_google_genai(
            prompt=self.prompt,
            image_paths=[],
            api_key=self.api_key,
            model_id="gemini-1.5-pro",
            aspect_ratio="1:1",
            resolution="1K"
        )

        MockGenaiClient.assert_called_once_with(api_key=self.api_key)
        mock_client_instance.models.generate_content.assert_called_once()
        self.assertIsInstance(result_image, Image.Image)

    def test_call_google_genai_no_api_key(self, mock_get):
        """测试未提供 API Key 时是否会引发 gr.Error"""
        with self.assertRaises(gr.Error) as context:
            api_client.call_google_genai(
                prompt=self.prompt,
                image_paths=[],
                api_key="",
                model_id="gemini-1.5-pro",
                aspect_ratio="1:1",
                resolution="1K"
            )
        self.assertIn("api_error_apiKey", str(context.exception))

    @patch('api_client.genai.Client')
    def test_call_google_genai_api_error(self, MockGenaiClient, mock_get):
        """测试 API 调用时发生异常的场景"""
        mock_client_instance = MockGenaiClient.return_value
        mock_client_instance.models.generate_content.side_effect = Exception("Network Error")

        with self.assertRaises(gr.Error) as context:
            api_client.call_google_genai(
                prompt=self.prompt,
                image_paths=[],
                api_key=self.api_key,
                model_id="gemini-1.5-pro",
                aspect_ratio="1:1",
                resolution="1K"
            )
        self.assertIn("api_error_system", str(context.exception))
        self.assertIn("Network Error", str(context.exception))

    # 最终修复：同时模拟外层和内层的 Pydantic 模型
    @patch('api_client.types.GenerateContentConfig')
    @patch('api_client.types.ImageConfig')
    @patch('api_client.Image.open', MagicMock())
    def test_get_model_config_logic(self, MockImageConfig, MockGenerateContentConfig, mock_get):
        """测试 _get_model_config 函数的内部逻辑 (最终修正版)"""
        
        # 场景1: gemini-1.5-flash (不应调用 ImageConfig)
        api_client._get_model_config("gemini-1.5-flash", "16:9", "2K")
        MockImageConfig.assert_not_called()
        # 验证 GenerateContentConfig 是用基础配置调用的
        MockGenerateContentConfig.assert_called_with(response_modalities=['IMAGE'])

        # 场景2: gemini-1.5-pro, 指定 AR
        api_client._get_model_config("gemini-1.5-pro", "16:9", "2K")
        MockImageConfig.assert_called_with(image_size="2K", aspect_ratio="16:9")
        # 验证 GenerateContentConfig 是用 ImageConfig 的模拟返回值调用的
        MockGenerateContentConfig.assert_called_with(
            response_modalities=["IMAGE"],
            image_config=MockImageConfig.return_value
        )

        # 场景3: gemini-1.5-pro, AR 为 "ar_none" (调用时不应包含 aspect_ratio)
        api_client._get_model_config("gemini-1.5-pro", "ar_none", "2K")
        MockImageConfig.assert_called_with(image_size="2K")
        MockGenerateContentConfig.assert_called_with(
            response_modalities=["IMAGE"],
            image_config=MockImageConfig.return_value
        )

    @patch('api_client.genai.Client')
    @patch('api_client.Image.open')
    def test_image_loading_logic(self, MockImageOpen, MockGenaiClient, mock_get):
        """测试加载本地参考图的逻辑"""
        mock_response = MagicMock()
        mock_part = MagicMock()
        mock_part.inline_data.data = self.fake_image_bytes
        mock_response.parts = [mock_part]
        mock_client_instance = MockGenaiClient.return_value
        mock_client_instance.models.generate_content.return_value = mock_response
        mock_image_instance = MagicMock(spec=Image.Image)
        MockImageOpen.return_value = mock_image_instance

        image_paths = ["/path/to/image1.png", "/path/to/image2.jpg"]
        api_client.call_google_genai(
            prompt=self.prompt,
            image_paths=image_paths,
            api_key=self.api_key,
            model_id="gemini-1.5-pro",
            aspect_ratio="1:1",
            resolution="1K"
        )

        self.assertEqual(MockImageOpen.call_count, 3)
        MockImageOpen.assert_any_call(image_paths[0])
        MockImageOpen.assert_any_call(image_paths[1])

        args, kwargs = mock_client_instance.models.generate_content.call_args
        sent_contents = kwargs['contents']
        self.assertEqual(len(sent_contents), 3)
        self.assertEqual(sent_contents[0], self.prompt)
        self.assertIs(sent_contents[1], mock_image_instance)
        self.assertIs(sent_contents[2], mock_image_instance)

if __name__ == '__main__':
    unittest.main()
