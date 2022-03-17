from json_config_parser import JsonConfigParser


class BotConfig:
    def __init__(self):
        self._channel_id = 0
        self._admin_channel_id = 0
        self._admins = []

    @property
    def channel_id(self):
        return self._channel_id

    @property
    def admin_channel_id(self):
        return self._admin_channel_id

    @property
    def admins(self):
        return self._admins

    class Parser(JsonConfigParser):
        def __init__(self, config_file):
            super().__init__(config_file, BotConfig)

        def _parse(self):
            self._config._channel_id = self._parse_key_as_int('channel_id')
            self._config._admin_channel_id = self._parse_key_as_int('admin_channel_id')
            self._parse_admins()

        def _parse_admins(self):
            admins_json = self._config_json['admins']
            for admin_json in admins_json:
                try:
                    self._config._admins.append(int(admin_json))
                except ValueError:
                    raise self.InvalidConfig(f"admins: Invalid admin ID - {admin_json}")

            self._config._admins = self._config_json['admins']

        def _validate_config(self):
            if self._config.channel_id == 0:
                raise self.InvalidConfig(f'Channel ID must be different than 0.')
