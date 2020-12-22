from typing import Dict
import boto3
import uuid
import json

# in order for boto3 to work, the config file paths must be set, look at .aws/README.md


class GroupExistsException(Exception):
    """Raised when the group already exists"""

    def __init__(self):
        super().__init__("The Group Name is Taken")


class MemberExistsException(Exception):
    """Raised when the group member already exists"""

    def __init__(self):
        super().__init__("The Member Name is Taken")


class Group:
    """
    Class to keep track of groups
    """

    def __init__(self, group_id: str, group_name: str, table_name: str = None) -> None:
        """
        Constructor for Group class, expects that the group already exists in groups table.
        If group does not exist in groups table then do not create a group object as
        the group will be created but the group id may get lost

        Params
        ------
        self: Group
        The group object

        group_id: str
        The group id that relates to the group, found in groups table

        group_name: str
        The name of the group

        table_name: str | None = None
        The name of the table, if none then main table will be used

        Returns
        -------
        None
        """
        # defines the id and group name
        self.group_id = group_id
        self.group_name = group_name

        # connect to table
        self.dynamodb, self.table = Group.connect(table_name)

    @staticmethod
    def connect(table_name: str = None):
        """
        Static function that connects to the correct dynamodb table

        Params
        ------

        table_name: str
        The table to connect to, if none then connects to main table

        Returns
        -------
        DynamoDB and Table Objects
        """
        # get resource
        dynamodb = boto3.resource("dynamodb")
        # get table
        table = (
            dynamodb.Table(table_name) if table_name else dynamodb.Table("group-todo")
        )

        return dynamodb, table

    @staticmethod
    def read_ids(json_file: str) -> Dict[str, str]:
        """
        Static function that reads ids from a JSON file

        Params
        ------

        json_file: str
        File with groups table

        Returns
        -------
        Dictionary of Group Names -> IDS
        """
        with open(json_file) as f:
            return json.load(f)

    @staticmethod
    def write_ids(ids: Dict[str, str], json_file: str) -> None:
        """
        Static function that saves ids to a JSON file

        Params
        ------

        ids: Dict[str, str]
        Dictionary that stores the ids

        json_file: str
        File with groups table
        
        Returns
        -------
        None
        """
        with open(json_file, "w") as f:
            json.dump(ids, f)

    @staticmethod
    def create_group(group_name: str, json_file: str, table_name: str = None) -> None:
        """
        Static function that creates a group to a dynamodb table and saves the group to a groups table

        Params
        ------

        group_name: str
        The name of the *new* group

        json_file: str
        File with groups table

        table_name: str | None = None
        The name of the table, if none then main table will be used

        Returns
        -------
        None
        """

        # read ids from table
        ids = Group.read_ids(json_file)

        # if id does not exist then create new one
        if group_name not in ids:
            ids[group_name] = str(uuid.uuid4())
        else:
            raise GroupExistsException

        # connect to table
        _, table = Group.connect(table_name)

        # add new group
        table.put_item(Item={"id": ids[group_name], "name": group_name})

        # write new ids
        Group.write_ids(ids, json_file)

    def add_user(self, name: str):
        """
        Method to add a new member to group, adds document for new member and updates document for the group

        Params
        ------

        self: Group
        The group object
        
        name: str
        The name of the *new* member

        Returns
        -------
        None or raises exception if member already exists

        """

        # create id
        id_ = str(uuid.uuid4())

        try:
            # update group document if member is not there
            self.table.update_item(
                Key={"id": self.group_id, "name": self.group_name},
                UpdateExpression="SET #name = :id",
                ConditionExpression="attribute_not_exists(#name)",
                ExpressionAttributeNames={"#name": name},
                ExpressionAttributeValues={":id": id_},
            )
        except Exception as ConditionalCheckFailedException:
            raise MemberExistsException

        # create member document
        self.table.put_item(Item={"id": id_, "name": name, "todo": []})

    def add_items(self, user: str, *items):
        # self.table.get_item
        pass


if __name__ == "__main__":
    ids = Group.read_ids("groups.json")
    test = Group(ids["test"], "test")

    test.add_user("Saad2")

    # Group.create_group('Test2', 'groups.json')
