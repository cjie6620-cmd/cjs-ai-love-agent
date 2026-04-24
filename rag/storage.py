"""MinIO 对象存储客户端：封装文件上传、下载、删除和预签名 URL 生成。

目的：提供统一的文件存储接口，支持知识文件的持久化存储、下载和临时访问链接生成。
当 MinIO 不可用时所有方法降级返回空/None，不阻塞上层流程。
"""

from __future__ import annotations

import io
import logging
import uuid
from datetime import timedelta

import urllib3

from core.config import get_settings

logger = logging.getLogger(__name__)


class MinioClient:
    """MinIO 对象存储客户端，支持文件上传、下载、删除和预签名 URL 生成。
    
    目的：封装MinIO 对象存储客户端，支持文件上传、下载、删除和预签名 URL 生成相关的调用能力与资源管理。
    结果：上层可通过统一客户端接口完成访问。
    """

    def __init__(self, *, log_startup: bool = True) -> None:
        """初始化 MinioClient。
        
        目的：初始化MinioClient所需的依赖、配置和初始状态。
        结果：实例创建完成后可直接参与后续业务流程。
        """
        self.settings = get_settings()
        self.bucket = self.settings.minio_bucket
        self._log_startup = log_startup

        try:
            from minio import Minio  # 延迟导入，避免缺失时阻塞模块加载

            self.client = Minio(
                endpoint=self.settings.minio_endpoint,
                access_key=self.settings.minio_access_key,
                secret_key=self.settings.minio_secret_key,
                secure=False,  # 本地开发使用 HTTP
                # 基础设施缺失时快速失败，避免本地测试被多次重试拖慢。
                http_client=urllib3.PoolManager(
                    timeout=urllib3.Timeout(connect=1.0, read=2.0),
                    retries=urllib3.Retry(total=0, connect=0, read=0, redirect=0),
                ),
            )
            self._ensure_bucket()
            self._available = True
            if self._log_startup:
                logger.info(
                    "MinIO 客户端初始化成功: endpoint=%s, bucket=%s",
                    self.settings.minio_endpoint,
                    self.bucket,
                )
        except Exception as exc:
            self._available = False
            if self._log_startup:
                logger.warning(
                    "MinIO 客户端初始化失败，文件存储功能降级: endpoint=%s, bucket=%s, error=%s",
                    self.settings.minio_endpoint,
                    self.bucket,
                    exc,
                )
            self.client = None  # type: ignore[assignment]

    def _ensure_bucket(self) -> None:
        """确保目标 bucket 存在，不存在则创建。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
            if self._log_startup:
                logger.info("创建 MinIO bucket: %s", self.bucket)

    def upload_file(
        self,
        data: bytes,
        filename: str,
        *,
        content_type: str = "application/octet-stream",
        prefix: str = "knowledge",
    ) -> str | None:
        """上传文件到 MinIO，返回对象键名（object_name）。

        目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        if not self._available:
            logger.warning("MinIO 不可用，跳过文件上传: %s", filename)
            return None

        try:
            # 生成唯一对象键：prefix/uuid_filename
            unique_id = uuid.uuid4().hex[:12]
            object_name = f"{prefix}/{unique_id}_{filename}"

            self.client.put_object(
                self.bucket,
                object_name,
                io.BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
            logger.info(
                "文件上传成功: bucket=%s, object=%s, size=%d", self.bucket, object_name, len(data)
            )
            return object_name
        except Exception as exc:
            logger.warning("MinIO 文件上传失败: %s", exc)
            return None

    def download_file(self, object_name: str) -> bytes | None:
        """从 MinIO 下载文件，返回文件二进制数据。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        if not self._available:
            logger.warning("MinIO 不可用，跳过文件下载: %s", object_name)
            return None

        try:
            response = self.client.get_object(self.bucket, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except Exception as exc:
            logger.warning("MinIO 文件下载失败: object=%s, error=%s", object_name, exc)
            return None

    def delete_file(self, object_name: str) -> bool:
        """从 MinIO 删除文件。

        目的：清理当前资源、连接或状态，避免残留副作用。
        结果：对象恢复到可控状态，降低资源泄漏和脏数据风险。
        """
        if not self._available:
            logger.warning("MinIO 不可用，跳过文件删除: %s", object_name)
            return False

        try:
            self.client.remove_object(self.bucket, object_name)
            logger.info("文件删除成功: bucket=%s, object=%s", self.bucket, object_name)
            return True
        except Exception as exc:
            logger.warning("MinIO 文件删除失败: object=%s, error=%s", object_name, exc)
            return False

    def get_presigned_url(
        self,
        object_name: str,
        *,
        expires: timedelta | None = None,
    ) -> str | None:
        """生成文件的预签名访问 URL。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        if not self._available:
            logger.warning("MinIO 不可用，跳过预签名 URL 生成: %s", object_name)
            return None

        try:
            url = self.client.presigned_get_object(
                self.bucket,
                object_name,
                expires=expires or timedelta(hours=1),
            )
            return url
        except Exception as exc:
            logger.warning("预签名 URL 生成失败: object=%s, error=%s", object_name, exc)
            return None
