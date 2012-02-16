import settings
import os
import os.path
import sys
import tempfile

# will create a client keystore with the debug and production certificates
# specified in the settings file. the keystore will be written to the file
# 'keystore' in the current directory. copy this file to /sdcard/odk/keystore
# on the device. additional certificates may be added by specifying their
# paths as command line arguments

KEYSTORE = 'keystore'
SHAM_PASSWORD = 'password'

def add_cert(i, cert):
    if os.path.samefile(cert, settings.DEFAULT_SSL_CERT):
        id = 'debug'
    else:
        id = 'prod%d' % i

    pemfile = tempfile.mkstemp(suffix='.pem')[1]
    os.popen('openssl x509 -in %s -out %s' % (cert, pemfile))
    os.popen('keytool -importcert -noprompt -alias %s -file %s -keystore %s -storetype BKS -provider org.bouncycastle.jce.provider.BouncyCastleProvider -providerpath %s -storepass %s' % (id, pemfile, KEYSTORE, settings.BOUNCYCASTLE_JAR, SHAM_PASSWORD))

if __name__ == "__main__":

    certs = set(crt for crt in [settings.DEFAULT_SSL_CERT, settings.SSL_CERT] if crt is not None)
    for arg in sys.argv[1:]:
        certs.add(arg)

    if os.path.exists(KEYSTORE):
        os.remove(KEYSTORE)

    for i, cert in enumerate(certs):
        print 'processing cert %s' % cert
        add_cert(i, cert)

    print 'keystore written to %s' % os.path.abspath(KEYSTORE)
