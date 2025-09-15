"""
Packet Processor for MW75 EEG Data

Handles parsing, validation, and processing of MW75 EEG data packets.
"""

import time
import struct
from typing import Optional, Tuple, Callable, List
from dataclasses import dataclass

from ..config import (
    EEG_EVENT_ID,
    PACKET_SIZE,
    SYNC_BYTE,
    EEG_SCALING_FACTOR,
    NUM_EEG_CHANNELS,
    CHECKSUM_ERROR_REPORT_INTERVAL,
)
from ..utils.logging import get_logger


@dataclass
class EEGPacket:
    """Represents a parsed EEG packet from MW75 device"""

    timestamp: float
    event_id: int
    counter: int
    ref: float
    drl: float
    channels: List[float]
    feature_status: int
    checksum_valid: bool


@dataclass
class ChecksumStats:
    """Tracks packet validation statistics"""

    valid_packets: int = 0
    invalid_packets: int = 0
    total_packets: int = 0

    @property
    def error_rate(self) -> float:
        """Calculate error rate as percentage"""
        return (self.invalid_packets / self.total_packets) * 100 if self.total_packets > 0 else 0.0


class PacketProcessor:
    """Handles MW75 packet parsing and validation"""

    def __init__(self, verbose: bool = False):
        self.stats = ChecksumStats()
        self.logger = get_logger(__name__)
        self.verbose = verbose
        self.buffer = bytearray()  # Continuous buffer across RFCOMM chunks

    def validate_checksum(self, packet: bytes) -> Tuple[bool, int, int]:
        """
        Validate MW75 packet checksum

        MW75 checksum calculation:
        - Sum of first 61 bytes (index 0-60)
        - Masked to 16 bits (& 0xFFFF)
        - Stored in bytes 61-62 as little endian

        Args:
            packet: 63-byte MW75 packet

        Returns:
            Tuple of (is_valid, calculated_checksum, received_checksum)
        """
        if len(packet) < PACKET_SIZE:
            return False, 0, 0

        calculated_checksum = sum(packet[:61]) & 0xFFFF
        received_checksum = packet[61] | (packet[62] << 8)
        is_valid = calculated_checksum == received_checksum

        return is_valid, calculated_checksum, received_checksum

    def parse_eeg_packet(self, packet: bytes) -> Optional[EEGPacket]:
        """
        Parse a 63-byte EEG packet into structured data

        Args:
            packet: 63-byte packet from MW75 device

        Returns:
            EEGPacket if successfully parsed and valid, None otherwise
        """
        if len(packet) != PACKET_SIZE or packet[0] != SYNC_BYTE:
            return None

        # Validate checksum
        is_valid, calc_checksum, recv_checksum = self.validate_checksum(packet)
        self.stats.total_packets += 1

        if not is_valid:
            self.stats.invalid_packets += 1
            if self.verbose:
                self.logger.warning(
                    f"Checksum mismatch! Calculated: 0x{calc_checksum:04x}, "
                    f"Received: 0x{recv_checksum:04x} (Event ID: {packet[1]}, Counter: {packet[3]})"
                )

            # Report statistics periodically (only in verbose mode)
            if self.verbose and self.stats.invalid_packets % CHECKSUM_ERROR_REPORT_INTERVAL == 0:
                self._log_checksum_stats()

            return None

        self.stats.valid_packets += 1

        # Parse packet structure
        event_id = packet[1]
        counter = packet[3]
        timestamp = time.time()

        # Extract REF and DRL values (already in correct units)
        ref = struct.unpack("<f", packet[4:8])[0]
        drl = struct.unpack("<f", packet[8:12])[0]

        # Extract 12 EEG channels with scaling
        channels = []
        for ch in range(NUM_EEG_CHANNELS):
            offset = 12 + (ch * 4)
            if offset + 4 <= len(packet):
                raw_value = struct.unpack("<f", packet[offset : offset + 4])[0]
                # Convert ADC values to microvolts
                scaled_value = raw_value * EEG_SCALING_FACTOR
                channels.append(scaled_value)

        feature_status = packet[60] if len(packet) > 60 else 0

        return EEGPacket(
            timestamp=timestamp,
            event_id=event_id,
            counter=counter,
            ref=ref,
            drl=drl,
            channels=channels,
            feature_status=feature_status,
            checksum_valid=True,
        )

    def _log_checksum_stats(self) -> None:
        """Log current checksum statistics"""
        invalid = self.stats.invalid_packets
        valid = self.stats.valid_packets
        error_rate = self.stats.error_rate

        self.logger.info(
            f"Checksum Stats: {valid} valid, {invalid} invalid, {error_rate:.1f}% error rate"
        )

    def process_data_buffer(
        self,
        data: bytes,
        eeg_callback: Callable[[EEGPacket], None],
        other_event_callback: Optional[Callable[[bytes], None]] = None,
    ) -> None:
        """
        Process data buffer and extract packets using continuous buffering

        This method accumulates data across RFCOMM chunks to handle packet framing
        correctly, since RFCOMM delivers arbitrary-sized chunks (e.g., 64 bytes)
        while EEG packets are exactly 63 bytes.

        Args:
            data: Raw data buffer from device
            eeg_callback: Function to call for EEG packets
            other_event_callback: Function to call for non-EEG packets
        """
        start_time = time.time()
        packets_processed = 0

        # Append new data to continuous buffer
        self.buffer.extend(data)
        initial_buffer_size = len(self.buffer)

        # Process all complete packets in buffer
        i = 0
        while i < len(self.buffer):
            # Look for sync byte to find packet boundaries
            if self.buffer[i] == SYNC_BYTE:
                # Check if we have enough data for a complete packet
                if i + PACKET_SIZE <= len(self.buffer):
                    packet = bytes(self.buffer[i : i + PACKET_SIZE])

                    # Validate checksum first so we don't skip valid alignments when payload
                    # contains a run of SYNC bytes (e.g., 0xAA). On checksum failure, advance
                    # by 1 byte instead of PACKET_SIZE.
                    is_valid, _, _ = self.validate_checksum(packet)
                    if not is_valid:
                        try:
                            # Keep stats/logging consistent for all packets by routing
                            # through parse_eeg_packet, which records checksum stats
                            # and exits early on invalid checksum without unpacking.
                            _ = self.parse_eeg_packet(packet)
                        except Exception as e:
                            self.logger.error(f"Error processing invalid packet: {e}")

                        i += 1  # slide window by 1 byte to avoid skipping a valid alignment
                        continue

                    try:
                        if packet[1] == EEG_EVENT_ID:  # EEG data
                            eeg_packet = self.parse_eeg_packet(packet)
                            if eeg_packet:
                                eeg_callback(eeg_packet)
                        else:  # Other event types
                            if other_event_callback:
                                other_event_callback(packet)

                        packets_processed += 1
                    except Exception as e:
                        self.logger.error(f"Error processing packet: {e}")

                    i += PACKET_SIZE
                else:
                    # Not enough data for complete packet, stop processing
                    break
            else:
                i += 1  # Search for next sync byte

        # Remove processed data from buffer, keep remaining partial data
        if i > 0:
            del self.buffer[:i]

        # Prevent buffer from growing too large (protect against sync byte loss)
        max_buffer_size = PACKET_SIZE * 10  # Allow up to 10 packets worth of data
        if len(self.buffer) > max_buffer_size:
            self.logger.warning(f"Buffer too large ({len(self.buffer)}B), truncating to find sync")
            # Try to find a sync byte in the last portion
            sync_pos = -1
            for j in range(len(self.buffer) - PACKET_SIZE, -1, -1):
                if self.buffer[j] == SYNC_BYTE:
                    sync_pos = j
                    break

            if sync_pos >= 0:
                del self.buffer[:sync_pos]
                self.logger.debug(f"Recovered sync at position {sync_pos}")
            else:
                self.buffer.clear()
                self.logger.warning("No sync byte found, clearing buffer")

        total_time = time.time() - start_time
        if total_time > 0.005 or packets_processed > 0:  # Log significant processing or any packets
            self.logger.debug(
                f"BUFFER: {initial_buffer_size}B+{len(data)}B → {len(self.buffer)}B remaining, {packets_processed} packets in {total_time * 1000:.2f}ms"
            )

    def get_final_stats(self) -> ChecksumStats:
        """
        Get final packet processing statistics

        Returns:
            ChecksumStats with current statistics
        """
        return self.stats
