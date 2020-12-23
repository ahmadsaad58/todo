from typing import Dict, List
import boto3
import uuid
import json

# in order for boto3 to work, the config file paths must be set, look at .aws/README.md


class MemberExistsException(Exception):
    """Raised when the group member already exists"""

    def __init__(self):
        super().__init__("The Member Name is Taken")


class MemberDoesNotExistsException(Exception):
    """Raised when the group member does not exists"""

    def __init__(self):
        super().__init__("The Member does not Exist")


class Group:
    """
    Class to keep track of groups
    """

    def __init__(
        self, group_name: str, table_name: str = None, json_file: str = "groups.json"
    ) -> None:
        """
        Constructor for Group class
        If group does not exist in groups table, then group will be created and stored in Group Table File

        Params
        ------
        self: Group
        The group object

        group_name: str
        The name of the group

        table_name: str | None = None
        The name of the table, if none then main table will be used

        json_file: str = 'groups.json'
        The name of the Group Table File, if none then main groups file will be used

        Returns
        -------
        None
        """
        # connect to table
        self.connect(table_name)

        # set the Group Table File
        self.json_file = json_file

        # read the ids in the Group Table File
        ids = Group.read_ids(self.json_file)

        # checks if group exists, if not create the group
        try:
            self.group_id = ids[group_name]
        except Exception as KeyError:
            self.group_id = self.create_group(group_name, ids)

        self.group_name = group_name

    def connect(self, table_name: str = None) -> None:
        """
        Connects to the correct dynamodb table

        Params
        ------

        self: Group
        The group object

        table_name: str
        The table to connect to, if none then connects to main table

        Returns
        -------
        None
        """
        # get resource
        self.dynamodb = boto3.resource("dynamodb")
        # get table
        self.table = (
            self.dynamodb.Table(table_name)
            if table_name
            else self.dynamodb.Table("group-todo")
        )

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

    def create_group(self, group_name: str, ids: Dict[str, str]) -> str:
        """
        Creates a group to a dynamodb table

        Params
        ------

        self: Group
        The group object

        group_name: str
        The name of the *new* group

        ids: Dict[str, str]
        Group Table as a dictionary

        Returns
        -------
        The id of *new* group
        """

        # create id for group
        ids[group_name] = str(uuid.uuid4())

        # add new group
        self.table.put_item(Item={"id": ids[group_name], "name": group_name})

        # write new ids
        Group.write_ids(ids, self.json_file)

        # return the id
        return ids[group_name]

    def delete_group(self) -> None:
        """
        Method to delete the group from table, remove document for the group

        Params
        ------

        self: Group
        The group object that will be deleted

        Returns
        -------
        None

        """

        # get the group document
        group = self.table.get_item(Key={"id": self.group_id, "name": self.group_name})

        members = [
            (group["Item"][attribute], attribute)
            for attribute in group["Item"]
            if attribute not in ("id", "name")
        ]

        for user_id, name in members:
            # remove member from table
            self.table.delete_item(Key={"id": user_id, "name": name})

        # remove group from table
        self.table.delete_item(Key={"id": self.group_id, "name": self.group_name})

        # delete the id
        ids = Group.read_ids(self.json_file)
        del ids[self.group_name]
        Group.write_ids(ids, self.json_file)

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

    def remove_user(self, name: str):
        """
        Method to remove a member from a group, remove document for member and updates document for the group

        Params
        ------

        self: Group
        The group object
        
        name: str
        The name of the member

        Returns
        -------
        None or raises exception if member does not exists

        """

        # get the group document
        group = self.table.get_item(Key={"id": self.group_id, "name": self.group_name})

        # get user_id to access user document
        try:
            user_id = group["Item"][name]
        except:
            raise MemberDoesNotExistsException

        # remove member from table
        self.table.delete_item(Key={"id": user_id, "name": name})

        # remove member from group document
        self.table.update_item(
            Key={"id": self.group_id, "name": self.group_name},
            UpdateExpression="REMOVE #name",
            ExpressionAttributeNames={"#name": name},
        )

    def add_items(self, username: str, *items: List[str]) -> None:
        """
        Method to add a new item to todo list, adds to list for a member document 

        Params
        ------

        self: Group
        The group object
        
        username: str
        The name of the member, raises exception if member does not exist

        *items: *args
        The items to add to the todo list

        Returns
        -------
        None or raises exception if member does not exist
        """

        # get the group document
        group = self.table.get_item(Key={"id": self.group_id, "name": self.group_name})

        # get user_id to access user document
        try:
            user_id = group["Item"][username]
        except:
            raise MemberDoesNotExistsException

        # add items to todo list
        # catch this if it fails
        self.table.update_item(
            Key={"id": user_id, "name": username},
            UpdateExpression="SET todo = list_append(todo, :item)",
            ExpressionAttributeValues={":item": items,},
        )

    def remove_items(self, username: str, *item_indices: List[int]) -> None:
        """
        Method to delete an item to todo list, removes from list for a member document 

        Params
        ------

        self: Group
        The group object
        
        username: str
        The name of the member, raises exception if member does not exist

        *items: *args
        The items to delete to the todo list, represented as ints

        Returns
        -------
        None or raises exception if member does not exist
        """

        # get the group document
        group = self.table.get_item(Key={"id": self.group_id, "name": self.group_name})

        # get user_id to access user document
        try:
            user_id = group["Item"][username]
        except:
            raise MemberDoesNotExistsException

        # build update expression
        update_expression = "REMOVE " + ", ".join(
            ["todo[{}]".format(num) for num in item_indices]
        )

        # remove items to todo list
        # catch this if it fails
        self.table.update_item(
            Key={"id": user_id, "name": username}, UpdateExpression=update_expression
        )


if __name__ == "__main__":
    print("creating group")
    test = Group("Test2")

    print("adding users in Test2 group")
    test.add_user("Saad")
    test.add_user("Saad2")
    test.add_user("Saad3")
    test.add_user("Saad4")

    input("adding items to each member, press enter to continue")
    test.add_items("Saad", "hello", "world")
    test.add_items("Saad2", "hello", "Saad")
    test.add_items("Saad3", "what", "ice cream")
    test.add_items("Saad4", "workout", "eat well", "wake up early", "shower")

    input("removing items for each member, press enter to contine")
    # removing more than the required items
    test.remove_items("Saad", 0, 1, 2)
    # removing the right amount of items
    test.remove_items("Saad2", 0, 1)
    # removing 1 item, cannot use negative indicies
    test.remove_items("Saad3", 1)
    # removing an item
    test.remove_items("Saad4", 1, 2)

    input("removing a user, press enter to continue")
    test.remove_user("Saad3")

    input("deleting group, table should be empty after this. Press enter to continue")
    test.delete_group()
