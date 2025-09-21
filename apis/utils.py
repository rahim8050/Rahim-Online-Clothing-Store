def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        # first IP in list
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
