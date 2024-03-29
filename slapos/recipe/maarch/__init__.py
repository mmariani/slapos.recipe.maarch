##############################################################################
#
# Copyright (c) 2012 Vifib SARL and Contributors. All Rights Reserved.
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsibility of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# guarantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

import ConfigParser
import errno
import lxml.etree
import md5
import os
import shutil

import psycopg2

from slapos.recipe.librecipe import GenericBaseRecipe



def xpath_set(xml, settings):
    for path, value in settings.iteritems():
        xml.xpath(path)[0].text = value


class Recipe(GenericBaseRecipe):
    """\
    This recipe configures a maarch instance to be ready to run,
    without going through the initial wizard:

     - creation of two xml files from the provided defaults
     - php.ini as required by Maarch
     - database setup.
     - a Maarch 'superadmin' user (with the same password as the Postgres user).

    Required options:
        php-ini
            full path to the PHP configuration file.
        htdocs
            full path to the htdocs directory.
        db-host
            ip address of the postgres server.
        db-port
            ip port of the postgres server.
        db-dbname
            postgres database name.
        db-username
            username to authenticate with postgres.
        db-password
            password to authenticate with postgres.
        language
            language to use with maarch (en or fr).
        root-docservers
            where to create docservers directories.
        sql_data_file
            path to data to be loaded in the DB (without the schema)

    Maarch configuration is detailed at
    http://wiki.maarch.org/Maarch_Framework_3/Setup_and_configuration_guide
    (beware: old document)
    """

    def install(self):
        if not self.options['db-port']:
            raise ValueError, "DB connection parameters are not ready yet"

        self.update_phpini(php_ini_path=self.options['php-ini'])

        self.load_initial_db()

        ret = []

        apps_config_xml = self.create_apps_config_xml()
        if apps_config_xml:
            ret.append(apps_config_xml)

        core_config_xml = self.create_core_config_xml()
        if core_config_xml:
            ret.append(core_config_xml)

        # confirm that everything is done, the app will run without further setup
        lck_path = self.installed_lock()
        ret.append(lck_path)

        return ret

    # explicitly call install upon update; the install method ought to be smart enough.
    update = install

    def create_apps_config_xml(self):
        options = self.options

        folder = os.path.join(options['htdocs'], 'apps/maarch_entreprise/xml')
        config_xml_default = os.path.join(folder, 'config.xml.default')
        config_xml = os.path.join(folder, 'config.xml')

        updating = os.path.exists(config_xml)

        if updating:
            # do not overwrite the config.xml file (it can be customized inside the application)
            config_xml_previous = config_xml
        else:
            config_xml_previous = config_xml_default

        content = open(config_xml_previous, 'rb').read()
        xml = lxml.etree.fromstring(content)

        xpath_set(xml, {
            'CONFIG/databaseserver': options['db-host'],
            'CONFIG/databaseserverport': options['db-port'],
            'CONFIG/databasename': options['db-dbname'],
            'CONFIG/databaseuser': options['db-username'],
            'CONFIG/databasepassword': options['db-password'],
            })

        if not updating:
            xpath_set(xml, {'CONFIG/lang': options['language']})

        with os.fdopen(os.open(config_xml, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600), 'w') as fout:
            fout.write(lxml.etree.tostring(xml, xml_declaration=True, encoding='utf-8').encode('utf-8'))

        return config_xml


    def create_core_config_xml(self):
        options = self.options

        folder = os.path.join(options['htdocs'], 'core/xml')
        config_xml_default = os.path.join(folder, 'config.xml.default')
        config_xml = os.path.join(folder, 'config.xml')

        if os.path.exists(config_xml):
            # do not overwrite the config.xml file (it can be customized inside the application)
            return

        content = open(config_xml_default, 'rb').read()
        xml = lxml.etree.fromstring(content)

        xpath_set(xml, {
            'CONFIG/defaultlanguage': options['language'],
            })

        with os.fdopen(os.open(config_xml, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600), 'w') as fout:
            fout.write(lxml.etree.tostring(xml, xml_declaration=True, encoding='utf-8').encode('utf-8'))

        return config_xml


    def update_phpini(self, php_ini_path):
        php_ini = ConfigParser.RawConfigParser()
        php_ini.read(php_ini_path)

        # Error Handling and Logging
        php_ini.set('PHP', 'error_reporting', 'E_ALL & ~E_DEPRECATED & ~E_NOTICE')
        php_ini.set('PHP', 'display_errors', 'on')
        # Data Handling
        php_ini.set('PHP', 'register_globals', 'off')
        # Allow short tags
        php_ini.set('PHP', 'short_open_tag', 'on')
        # Html Charset
        php_ini.set('PHP', 'default_charset', 'UTF-8')
        #  Magic Quotes
        php_ini.set('PHP', 'magic_quotes_gpc', 'off')
        php_ini.set('PHP', 'magic_quotes_runtime', 'off')
        php_ini.set('PHP', 'magic_quotes_sybase', 'off')

        with os.fdopen(os.open(php_ini_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600), 'w') as fout:
            php_ini.write(fout)


    def load_initial_db(self):
        """
        This method:

         - creates the initial schema
         - patches the schema for ipv6
         - loads initial data
         - sets initial superadmin password
         - configures and creates docservers directories
        """

        options = self.options

        conn = psycopg2.connect(host = options['db-host'],
                                port = int(options['db-port']),
                                database = options['db-dbname'],
                                user = options['db-username'],
                                password = options['db-password'])

        cur = conn.cursor()

        # skip everything if the tables have already been created
        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='docservers';")
        if cur.rowcount == 1:
            conn.close()
            return

        htdocs = options['htdocs']

        # load the schema
        with open(os.path.join(htdocs, 'structure.sql')) as fin:
            cur.execute(fin.read())

        # patch the schema to store long addresses (ipv6)
        cur.execute('ALTER TABLE HISTORY ALTER COLUMN remote_ip TYPE VARCHAR(255);')


        sql_data_file = options['maarch-sql-data-file']
        if sql_data_file == 'null':     # workaround for proxy bug
            sql_data_file = ''

        with open(os.path.join(htdocs, sql_data_file or 'data_mini.sql')) as fin:
            cur.execute(fin.read())

        # initial admin password
        enc_password = md5.md5(options['db-password']).hexdigest()
        cur.execute("UPDATE users SET password=%s WHERE user_id='superadmin';", (enc_password, ))

        self.update_docservers(cur)

        conn.commit()
        cur.close()
        conn.close()


    def update_docservers(self, cur):
        # directories described in http://wiki.maarch.org/Maarch_Entreprise/fr/Man/Admin/Stockage

        root_docservers = self.options['root-docservers']

        for docserver_id, foldername in [
                ('OFFLINE_1', 'offline'),
                ('FASTHD_AI', 'ai'),
                ('OAIS_MAIN_1', 'OAIS_main'),
                ('OAIS_SAFE_1', 'OAIS_safe'),
                ('FASTHD_MAN', 'manual'),
                ('TEMPLATES', 'templates'),
                ]:
            dst_path = os.path.join(root_docservers, foldername)
            cur.execute('UPDATE docservers SET path_template=%s WHERE docserver_id=%s', (dst_path, docserver_id))
            try:
                os.makedirs(dst_path)
            except OSError as exc:
                if exc.errno == errno.EEXIST:
                    pass
                else:
                    raise


    def installed_lock(self):
        """\
        Create an empty file to mean the setup is completed
        """
        lck_path = os.path.join(self.options['htdocs'], 'installed.lck')

        with open(lck_path, 'w'):
            pass

        return lck_path

