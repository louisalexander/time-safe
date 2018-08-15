package org.louis;

import org.apache.commons.crypto.stream.CryptoInputStream;
import org.apache.commons.crypto.stream.CryptoOutputStream;

import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Properties;

public class EncryptDecrypt implements AutoCloseable {

    private static final SecretKeySpec key = new SecretKeySpec(getUTF8Bytes("1234567890123456"), "AES");
    private static final IvParameterSpec iv = new IvParameterSpec(getUTF8Bytes("1234567890123456"));
    private static final String transform = "AES/CBC/PKCS5Padding";
    private static final Properties properties = new Properties();

    private static byte[] getUTF8Bytes(String input) {
        return input.getBytes(StandardCharsets.UTF_8);
    }

    public static byte[] encrypt(String input) throws IOException {

        ByteArrayOutputStream outputStream = new ByteArrayOutputStream();

        try (CryptoOutputStream cos = new CryptoOutputStream(transform, properties, outputStream, key, iv)) {
            cos.write(getUTF8Bytes(input));
            cos.flush();
        }

        return outputStream.toByteArray();
    }

    public static String decrypt(byte[] encrypted) throws IOException {
        // Decryption with CryptoInputStream.
        InputStream inputStream = new ByteArrayInputStream(encrypted);

        try (CryptoInputStream cis = new CryptoInputStream(transform, properties, inputStream, key, iv)) {
            byte[] decryptedData = new byte[1024];
            int decryptedLen = 0;
            int i;
            while ((i = cis.read(decryptedData, decryptedLen, decryptedData.length - decryptedLen)) > -1) {
                decryptedLen += i;
            }
            return new String(decryptedData, 0, decryptedLen, StandardCharsets.UTF_8);
        }
    }

    @Override
    public void close() throws Exception {

    }
}
