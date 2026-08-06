"""
CRC utilities for DatouBoss / WatchPower protocol.
Compatible with the CRC used by Voltronic / WatchPower.

Each command is sent as:

    ASCII command + CRC (2 bytes) + CR (0x0D)
"""

from __future__ import annotations


class CRC:
    """CRC helper for DatouBoss protocol."""

    @staticmethod
    def calculate(data: bytes) -> int:
        """
        Calculate CRC-CCITT (XMODEM) and apply the same byte escaping
        as WatchPower.

        Returns:
            16-bit integer.
        """

        crc = 0

        for byte in data:
            crc ^= byte << 8

            for _ in range(8):
                if crc & 0x8000:
                    crc = ((crc << 1) ^ 0x1021) & 0xFFFF
                else:
                    crc = (crc << 1) & 0xFFFF

        high = (crc >> 8) & 0xFF
        low = crc & 0xFF

        #
        # Same correction as CRCUtil.java
        #
        if low in (0x28, 0x0D, 0x0A):
            low += 1

        if high in (0x28, 0x0D, 0x0A):
            high += 1

        return (high << 8) | low

    @staticmethod
    def to_bytes(data: bytes) -> bytes:
        """
        Return CRC as two bytes (High, Low).
        """

        crc = CRC.calculate(data)

        return bytes([
            (crc >> 8) & 0xFF,
            crc & 0xFF,
        ])

    @staticmethod
    def append(command: str) -> bytes:
        """
        Build a complete command frame.

        Example:

            QPIGS + CRC + CR
        """

        payload = command.encode("ascii")

        return payload + CRC.to_bytes(payload) + b"\r"

    @staticmethod
    def verify(frame: bytes) -> bool:
        """
        Verify a received frame.

        The frame must contain:
            payload + crc
        (without trailing CR)
        """

        if len(frame) < 3:
            return False

        payload = frame[:-2]

        received = int.from_bytes(frame[-2:], "big")

        expected = CRC.calculate(payload)

        return received == expected


if __name__ == "__main__":

    tests = [
        "QPI",
        "QPIRI",
        "QPIGS",
        "QMOD",
        "QID",
        "QPIWS",
        "QFLAG",
    ]

    for command in tests:

        packet = CRC.append(command)

        print("-" * 50)
        print(command)
        print(packet.hex(" "))
