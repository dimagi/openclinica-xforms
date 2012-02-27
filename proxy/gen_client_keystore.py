import settings
import os
import os.path
import sys
import tempfile
import ssl
from urlparse import urlparse

# will create a client keystore with the debug and production certificates
# specified in the settings file. the keystore will be written to the file
# 'keystore' in the current directory. copy this file to /sdcard/odk/keystore
# on the device. additional certificates may be added by specifying their
# paths as command line arguments

KEYSTORE = 'keystore.bks'
SHAM_PASSWORD = 'password'

def tmp_pemfile():
    return tempfile.mkstemp(suffix='.pem')[1]

def add_cert(i, cert):
    if cert.startswith('http') and '://' in cert:
        pemfile, namefunc = cert_from_web(cert)
    else:
        pemfile, namefunc = cert_from_file(cert)

    os.popen('keytool -importcert -noprompt -alias %s -file %s -keystore %s -storetype BKS -provider org.bouncycastle.jce.provider.BouncyCastleProvider -providerpath %s -storepass %s' % (namefunc(i), pemfile, KEYSTORE, settings.BOUNCYCASTLE_JAR, SHAM_PASSWORD))

def cert_from_file(path):
    def cert_id(i):
        if os.path.samefile(path, settings.DEFAULT_SSL_CERT):
            return 'debug'
        else:
            return 'prod%d' % i

    pemfile = tmp_pemfile()
    os.popen('openssl x509 -in %s -out %s' % (path, pemfile))
    return pemfile, cert_id

def cert_from_web(url):
    up = urlparse(url)
    cert = ssl.get_server_certificate((up.hostname, up.port or 443))
    # fix formatting for certificate so keytool likes it
    cert = '\n-----END CERT'.join(cert.split('-----END CERT'))

    pemfile = tmp_pemfile()
    with open(pemfile, 'w') as f:
        f.write(cert)

    return pemfile, lambda i: 'web%d' % i

if __name__ == "__main__":

    certs = set(crt for crt in [settings.DEFAULT_SSL_CERT, settings.SSL_CERT, settings.OPENCLINICA_SERVER] if crt is not None)
    certs |= set(sys.argv[1:])

    if os.path.exists(KEYSTORE):
        os.remove(KEYSTORE)

    for i, cert in enumerate(certs):
        print 'processing cert %s' % cert
        add_cert(i, cert)

    print 'keystore written to %s' % os.path.abspath(KEYSTORE)
