from autologin_middleware import AutologinMiddleware


class DDAutologinMiddleware(AutologinMiddleware):
    def needs_login(self, request, spider):
        return bool(spider.queue.get_login_credentials(request.url))

    def login_request(self, request, spider):
        creds = spider.queue.get_login_credentials(request.url)
        if creds:
            request.meta['autologin_login_url'] = creds['url']
            request.meta['autologin_username'] = creds['login']
            request.meta['autologin_password'] = creds['password']
        return super().login_request(request, spider)
