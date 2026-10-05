from django.core.files.uploadhandler import FileUploadHandler, StopUpload


class RegistrationUploadLimitHandler(FileUploadHandler):
    """Hard stream bounds, before uploaded files are buffered to memory/disk."""

    def __init__(self, request=None):
        super().__init__(request)
        self.enabled = request is not None
        self.per_file = (
            5 * 1024 * 1024
            if request is not None and request.path.startswith("/locations/import/")
            else 20 * 1024 * 1024
        )
        self.total = self.current = self.files = 0

    def new_file(self, *args, **kwargs):
        super().new_file(*args, **kwargs)
        self.current = 0
        self.files += 1
        if self.enabled and self.files > 9:
            self.request.registration_upload_rejected = True
            raise StopUpload(connection_reset=False)

    def receive_data_chunk(self, raw_data, start):
        self.current += len(raw_data)
        self.total += len(raw_data)
        if self.enabled and (self.current > self.per_file or self.total > 100 * 1024 * 1024):
            self.request.registration_upload_rejected = True
            raise StopUpload(connection_reset=False)
        return raw_data

    def file_complete(self, file_size):
        return None
