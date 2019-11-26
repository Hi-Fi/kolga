# flake8: noqa
# type: ignore

# Almost a carbon copy of SQLAlchemy database URL parsing.
# Dependencies on SQLAchemies internals has been stripped
# out in favor of internal Python functions and exceptions
# have been changed to raise ValueError instead of ArgumentError,
# an exception only found in SQLAlchemy.
#
# SQLAlchemy has not made changes to this functionality since 2012
# at the time of initial introduction to this code base.
#
# Original source can be found at:
# https://github.com/ContextLogic/sqlalchemy/blob/master/engine/url.py

"""Provides the URL class which encapsulates
information about a database connection specification.

The URL object is created automatically when :func:`~sqlalchemy.engine.create_engine` is called
with a string argument; alternatively, the URL is a public-facing construct which can
be used directly and is also accepted directly by ``create_engine()``.
"""

import re
import urllib
import urllib.parse
from typing import Any, Dict, Optional, Set


class URL(object):
    """
    Represent the components of a URL used to connect to a database.

    This object is suitable to be passed directly to a
    ``create_engine()`` call.  The fields of the URL are parsed from a
    string by the ``module-level make_url()`` function.  the string
    format of the URL is an RFC-1738-style string.

    All initialization parameters are available as public attributes.

    :param drivername: the name of the database backend.
      This name will correspond to a module in sqlalchemy/databases
      or a third party plug-in.

    :param username: The user name.

    :param password: database password.

    :param host: The name of the host.

    :param port: The port number.

    :param database: The database name.

    :param query: A dictionary of options to be passed to the
      dialect and/or the DBAPI upon connect.

    """

    def __init__(
        self,
        drivername,
        username: Optional[str] = None,
        password: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        query: Dict[Any, Any] = None,
    ) -> None:
        self.port: Optional[int]
        self.drivername = drivername
        self.username = username
        self.password = password
        self.host = host
        if port is not None:
            self.port = int(port)
        else:
            self.port = None
        self.database = database
        self.query: Dict[Any, Any] = query or {}

    def __str__(self) -> str:
        s = self.drivername + "://"
        if self.username is not None:
            s += self.username
            if self.password is not None:
                s += ":" + urllib.parse.quote_plus(self.password)
            s += "@"
        if self.host is not None:
            s += self.host
        if self.port is not None:
            s += ":" + str(self.port)
        if self.database is not None:
            s += "/" + self.database
        if self.query:
            keys = sorted(self.query.keys())
            s += "?" + "&".join("%s=%s" % (k, self.query[k]) for k in keys)
        return s

    def __hash__(self) -> int:
        return hash(str(self))

    def __eq__(self, other) -> bool:
        return (
            isinstance(other, URL)
            and self.drivername == other.drivername
            and self.username == other.username
            and self.password == other.password
            and self.host == other.host
            and self.database == other.database
            and self.query == other.query
        )

    def get_dialect(self):
        """Return the SQLAlchemy database dialect class corresponding
        to this URL's driver name.
        """

        try:
            if "+" in self.drivername:
                dialect, driver = self.drivername.split("+")
            else:
                dialect, driver = self.drivername, "base"

            module = __import__("sqlalchemy.dialects.%s" % (dialect,)).dialects
            module = getattr(module, dialect)
            if hasattr(module, driver):
                module = getattr(module, driver)
            else:
                module = self._load_entry_point()
                if module is None:
                    raise ValueError(
                        "Could not determine dialect for '%s'." % self.drivername
                    )

            return module.dialect
        except ImportError:
            module = self._load_entry_point()
            if module is not None:
                return module
            else:
                raise ValueError(
                    "Could not determine dialect for '%s'." % self.drivername
                )

    def _load_entry_point(self):
        """attempt to load this url's dialect from entry points, or return None
        if pkg_resources is not installed or there is no matching entry point.

        Raise ImportError if the actual load fails.

        """
        try:
            import pkg_resources
        except ImportError:
            return None

        for res in pkg_resources.iter_entry_points("sqlalchemy.dialects"):
            if res.name == self.drivername.replace("+", "."):
                return res.load()
        else:
            return None

    def translate_connect_args(self, names=None, **kw):
        """Translate url attributes into a dictionary of connection arguments.

        Returns attributes of this url (`host`, `database`, `username`,
        `password`, `port`) as a plain dictionary.  The attribute names are
        used as the keys by default.  Unset or false attributes are omitted
        from the final dictionary.

        :param kw: Optional, alternate key names for url attributes.

        :param names: Deprecated.  Same purpose as the keyword-based alternate names,
            but correlates the name to the original positionally.
        """

        if not names:
            names = []
        translated = {}
        attribute_names = ["host", "database", "username", "password", "port"]
        for sname in attribute_names:
            if names:
                name = names.pop(0)
            elif sname in kw:
                name = kw[sname]
            else:
                name = sname
            if name is not None and getattr(self, sname, False):
                translated[name] = getattr(self, sname)
        return translated


def make_url(name_or_url: str) -> URL:
    """Given a string or unicode instance, produce a new URL instance.

    The given string is parsed according to the RFC 1738 spec.  If an
    existing URL object is passed, just returns the object.
    """
    return _parse_rfc1738_args(name_or_url)


def _parse_rfc1738_args(name):
    pattern = re.compile(
        r"""
            (?P<name>[\w\+]+)://
            (?:
                (?P<username>[^:/]*)
                (?::(?P<password>[^/]*))?
            @)?
            (?:
                (?P<host>[^/:]*)
                (?::(?P<port>[^/]*))?
            )?
            (?:/(?P<database>.*))?
            """,
        re.X,
    )

    m = pattern.match(name)
    if m is not None:
        components = m.groupdict()
        if components["database"] is not None:
            tokens = components["database"].split("?", 2)
            components["database"] = tokens[0]
            query = (
                len(tokens) > 1 and dict(urllib.parse.parse_qsl(tokens[1]))
            ) or None
            # Py2K
            if query is not None:
                query = dict((k.encode("ascii"), query[k]) for k in query)
            # end Py2K
        else:
            query = None
        components["query"] = query

        if components["password"] is not None:
            components["password"] = urllib.parse.unquote_plus(components["password"])

        name = components.pop("name")
        return URL(name, **components)
    else:
        raise ValueError("Could not parse rfc1738 URL from string '%s'" % name)