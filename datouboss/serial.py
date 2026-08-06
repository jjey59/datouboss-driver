"""
datouboss.serial

Communication série avec les onduleurs DatouBoss / WatchPower.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import serial

from .crc import CRC


_LOGGER = logging.getLogger(__name__)


class SerialCommunicationError(Exception):
    """Erreur de communication série."""


class CRCError(Exception):
    """CRC invalide reçu depuis l'onduleur."""


class SerialHandler:
    """
    Gestionnaire de communication série.

    Cette classe reproduit le comportement de WatchPower :

        - ouverture du port
        - envoi des commandes
        - lecture des réponses
        - vérification du CRC
        - reconnexion automatique
    """

    DEFAULT_BAUDRATE = 2400
    DEFAULT_TIMEOUT = 2.0
    DEFAULT_RETRIES = 3

    def __init__(
        self,
        port: str,
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
    ) -> None:

        self._port_name = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._retries = retries

        self._serial: Optional[serial.Serial] = None

        _LOGGER.debug(
            "SerialHandler créé (port=%s baudrate=%d timeout=%.1fs)",
            port,
            baudrate,
            timeout,
        )

    @property
    def is_connected(self) -> bool:
        """Retourne True si le port est ouvert."""

        return (
            self._serial is not None
            and self._serial.is_open
        )
        def connect(self) -> None:
        """
        Ouvre le port série si nécessaire.
        """

        if self.is_connected:
            return

        try:
            _LOGGER.info(
                "Ouverture du port série %s (%d bauds)",
                self._port_name,
                self._baudrate,
            )

            self._serial = serial.Serial(
                port=self._port_name,
                baudrate=self._baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self._timeout,
                write_timeout=self._timeout,
            )

            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()

            _LOGGER.info("Connexion série établie.")

        except serial.SerialException as err:
            self._serial = None
            raise SerialCommunicationError(
                f"Impossible d'ouvrir {self._port_name}"
            ) from err

    def disconnect(self) -> None:
        """
        Ferme proprement le port série.
        """

        if not self.is_connected:
            return

        _LOGGER.info("Fermeture du port série.")

        try:
            self._serial.close()

        finally:
            self._serial = None

    def reconnect(self) -> None:
        """
        Force une reconnexion.
        """

        _LOGGER.warning("Reconnexion du port série...")

        self.disconnect()

        time.sleep(0.5)

        self.connect()

    def __enter__(self):
        """
        Support du contexte :

            with SerialHandler(...) as serial:
                ...
        """

        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        """
        Fermeture automatique du port.
        """

        self.disconnect()

    def flush(self) -> None:
        """
        Vide les buffers RX/TX.
        """

        if not self.is_connected:
            raise SerialCommunicationError("Port série non connecté.")

        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()

    def _ensure_connected(self) -> None:
        """
        Vérifie que le port est ouvert.
        """

        if not self.is_connected:
            self.connect()
        def _read_frame(self) -> bytes:
        """
        Lit une trame jusqu'au caractère CR (0x0D).

        Retourne les données sans le CR final.
        """

        if not self.is_connected:
            raise SerialCommunicationError("Port série non connecté.")

        buffer = bytearray()

        start = time.monotonic()

        while True:

            if (time.monotonic() - start) > self._timeout:
                raise TimeoutError("Temps d'attente dépassé.")

            byte = self._serial.read(1)

            if not byte:
                continue

            if byte == b"\r":
                break

            buffer.extend(byte)

        return bytes(buffer)

    def _write_frame(self, command: str) -> None:
        """
        Envoie une commande à l'onduleur.

        Format :

            ASCII + CRC + CR
        """

        if not self.is_connected:
            raise SerialCommunicationError("Port série non connecté.")

        frame = CRC.append(command)

        self.flush()

        _LOGGER.debug(
            "TX %s -> %s",
            command,
            frame.hex(" "),
        )

        self._serial.write(frame)
        self._serial.flush()

    def query(self, command: str) -> str:
        """
        Envoie une commande et retourne la réponse ASCII.

        Trois tentatives sont effectuées avant abandon.
        """

        last_error = None

        for attempt in range(1, self._retries + 1):

            try:

                self._ensure_connected()

                self._write_frame(command)

                frame = self._read_frame()

                _LOGGER.debug(
                    "RX %s",
                    frame.hex(" "),
                )

                if not CRC.verify(frame):
                    raise CRCError(
                        f"CRC invalide (tentative {attempt})"
                    )

                payload = frame[:-2]

                response = payload.decode(
                    "ascii",
                    errors="ignore",
                )

                _LOGGER.debug(
                    "%s -> %s",
                    command,
                    response,
                )

                return response

            except Exception as exc:

                last_error = exc

                _LOGGER.warning(
                    "Tentative %d/%d échouée (%s)",
                    attempt,
                    self._retries,
                    exc,
                )

                self.reconnect()

        raise SerialCommunicationError(
            f"Impossible d'exécuter la commande {command}"
        ) from last_error
