from autologin_middleware import AutologinMiddleware


class DDAutologinMiddleware(AutologinMiddleware):
    def needs_login(self, request, spider):
        return spider.queue.has_login_credentials(request.url)
