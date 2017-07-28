from autologin_middleware import AutologinMiddleware


# TODO - weakref cache for login credentials


class DDAutologinMiddleware(AutologinMiddleware):
    def needs_login(self, request, spider):
        result = bool(spider.queue.get_login_credentials(request.url))
        print('needs_login', request, result)
        return result

    def login_request(self, request, spider):
        creds = spider.queue.get_login_credentials(request.url)
        if creds:
            request.meta['autologin_login_url'] = creds['url']
            request.meta['autologin_username'] = creds['login']
            request.meta['autologin_password'] = creds['password']
        return super().login_request(request, spider)
