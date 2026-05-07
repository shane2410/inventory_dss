import cgi
import re


if not hasattr(cgi, "valid_boundary"):
	_boundary_re = re.compile(r"^[ -~]{0,200}[!-~]$")

	def _valid_boundary(boundary):
		if isinstance(boundary, bytes):
			try:
				boundary = boundary.decode("ascii")
			except UnicodeDecodeError:
				return False
		if not isinstance(boundary, str):
			return False
		return _boundary_re.match(boundary) is not None

	cgi.valid_boundary = _valid_boundary
