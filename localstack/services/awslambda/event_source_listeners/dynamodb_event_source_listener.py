import datetime
from typing import Any, Dict, List, Optional

from localstack.services.awslambda.event_source_listeners.stream_event_source_listener import (
    StreamEventSourceListener,
)
from localstack.services.awslambda.lambda_api import get_event_sources
from localstack.utils.aws import aws_stack
from localstack.utils.common import first_char_to_lower


class DynamoDBEventSourceListener(StreamEventSourceListener):
    _FAILURE_PAYLOAD_DETAILS_FIELD_NAME = "DDBStreamBatchInfo"

    @staticmethod
    def get_source_type() -> Optional[str]:
        return "dynamodb"

    def _get_matching_event_sources(self) -> List[Dict]:
        event_sources = get_event_sources(source_arn=r".*:dynamodb:.*")
        return [source for source in event_sources if source["State"] == "Enabled"]

    def _get_stream_client(self, region_name):
        return aws_stack.connect_to_service("dynamodbstreams", region_name=region_name)

    def _get_stream_description(self, stream_client, stream_arn):
        return stream_client.describe_stream(StreamArn=stream_arn)["StreamDescription"]

    def _get_shard_iterator(self, stream_client, stream_arn, shard_id, iterator_type):
        return stream_client.get_shard_iterator(
            StreamArn=stream_arn, ShardId=shard_id, ShardIteratorType=iterator_type
        )["ShardIterator"]

    def _create_lambda_event_payload(self, stream_arn, records, shard_id=None):
        record_payloads = []
        for record in records:
            record_payload = {}
            for key, val in record.items():
                record_payload[first_char_to_lower(key)] = val
            creation_time = record_payload.get("dynamodb", {}).get(
                "ApproximateCreationDateTime", None
            )
            if creation_time is not None:
                record_payload["dynamodb"]["ApproximateCreationDateTime"] = (
                    creation_time.timestamp() * 1000
                )
            record_payloads.append(
                {
                    "eventID": record_payload.pop("eventID"),
                    "eventVersion": "1.0",
                    "awsRegion": aws_stack.get_region(),
                    "eventName": record_payload.pop("eventName"),
                    "eventSourceARN": stream_arn,
                    "eventSource": "aws:dynamodb",
                    "dynamodb": record_payload,
                }
            )
        return {"Records": record_payloads}

    def _get_starting_and_ending_sequence_numbers(self, first_record, last_record):
        return first_record["dynamodb"]["SequenceNumber"], last_record["dynamodb"]["SequenceNumber"]

    def _get_first_and_last_arrival_time(self, first_record, last_record):
        return (
            first_record.get("ApproximateArrivalTimestamp", datetime.datetime.utcnow()),
            last_record.get("ApproximateArrivalTimestamp", datetime.datetime.utcnow()),
        )

    def process_event(self, event: Any):
        raise NotImplementedError
