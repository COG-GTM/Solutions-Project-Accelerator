import numbers
import re
from string import Formatter


def to_db_id(value, name='id'):
    """Return ``value`` as a non-negative int, or raise ValueError for anything else."""
    if isinstance(value, bool):
        raise ValueError('Invalid {}: {!r}'.format(name, value))
    if isinstance(value, numbers.Integral):
        result = int(value)
    elif isinstance(value, numbers.Real) and float(value).is_integer():
        result = int(value)
    elif isinstance(value, str) and re.fullmatch(r'\s*\d+(\.0+)?\s*', value):
        result = int(float(value))
    else:
        raise ValueError('Invalid {}: {!r}'.format(name, value))
    if result < 0:
        raise ValueError('Invalid {}: {!r}'.format(name, value))
    return result


def bind_params(param_names, **values):
    """Order ``values`` to match a template's ``*_params`` tuple of ``?`` placeholders."""
    params = []
    for param_name in param_names:
        value = values[param_name]
        if value is None:
            params.append(None)
        elif param_name in INT_PARAMS:
            params.append(to_db_id(value, param_name))
        else:
            params.append(str(value))
    return tuple(params)


def render_name_template(template, values):
    """Fill a library sub-object name template such as ``Step_{Index}`` using only plain ``{field}`` lookups."""
    result = []
    for literal, field_name, format_spec, conversion in Formatter().parse(template):
        result.append(literal)
        if field_name is None:
            continue
        if not re.fullmatch(r'\w+', field_name) or field_name not in values or conversion or format_spec:
            raise ValueError('Unsupported name template field: {!r}'.format(field_name))
        result.append(str(values[field_name]))
    return ''.join(result)


INT_PARAMS = {'project_id', 'controller_id', 'parent_object_id', 'factory_talk_view_se_id', 'object_id',
              'subobject_id', 'control_module_id', 'ref_type', 'description_override'}

_FILTER_TOKEN = re.compile(
    r"\s*(?:(?P<column>[A-Za-z_]\w*\.[A-Za-z_]\w*)"
    r"|(?P<string>'(?:[^']|'')*')"
    r"|(?P<number>-?\d+(?:\.\d+)?)"
    r"|(?P<operator><>|!=|>=|<=|=|<|>)"
    r"|(?P<word>[A-Za-z]+))")
_FILTER_COLUMNS = {
    'registeredlibraries': ('RegisteredLibraries', (
        'LibraryID', 'Name', 'LibraryType', 'Category', 'CoreType', 'Version', 'Description')),
    'objects': ('Objects', ('Name', 'LibraryType', 'CatalogNumber', 'Description')),
    'subobjects': ('SubObjects', ('Name', 'DisplayName', 'Type', 'Description')),
}


def _filter_column(column):
    table, _, name = column.partition('.')
    entry = _FILTER_COLUMNS.get(table.lower())
    if entry:
        for allowed in entry[1]:
            if allowed.lower() == name.lower():
                return '{}.{}'.format(entry[0], allowed)
    raise ValueError('Unsupported ACM filter column: {!r}'.format(column))


def parameterize_acm_filter(filter_expression):
    """
    Convert an ACM library filter such as ``Library.LibraryType='HMI' And Library.Category='Display'``
    (after table names are mapped) into a SQL fragment with ``?`` placeholders plus its parameters.

    Only ``Table.Column <op> literal`` comparisons joined by AND/OR are accepted; anything else raises
    ValueError so library files cannot inject SQL.
    """
    if filter_expression is None or not str(filter_expression).strip():
        return '', ()
    text = str(filter_expression).strip()
    tokens = []
    pos = 0
    while pos < len(text):
        match = _FILTER_TOKEN.match(text, pos)
        if not match or match.end() == pos:
            raise ValueError('Unsupported ACM filter: {!r}'.format(filter_expression))
        pos = match.end()
        tokens.append((match.lastgroup, match.group(match.lastgroup)))

    clauses = []
    params = []
    index = 0
    while True:
        if index + 3 > len(tokens):
            raise ValueError('Unsupported ACM filter: {!r}'.format(filter_expression))
        (kind_col, column), (kind_op, operator), (kind_val, value) = tokens[index:index + 3]
        if kind_col != 'column':
            raise ValueError('Unsupported ACM filter column: {!r}'.format(column))
        column = _filter_column(column)
        if kind_op == 'word' and operator.upper() == 'LIKE':
            operator = 'LIKE'
        elif kind_op != 'operator':
            raise ValueError('Unsupported ACM filter operator: {!r}'.format(operator))
        if kind_val == 'string':
            params.append(value[1:-1].replace("''", "'"))
        elif kind_val == 'number':
            params.append(value)
        else:
            raise ValueError('Unsupported ACM filter value: {!r}'.format(value))
        clauses.append('{} {} ?'.format(column, operator))
        index += 3
        if index == len(tokens):
            break
        kind_join, join = tokens[index]
        if kind_join != 'word' or join.upper() not in ('AND', 'OR'):
            raise ValueError('Unsupported ACM filter: {!r}'.format(filter_expression))
        clauses.append(join.upper())
        index += 1
    return 'and (' + ' '.join(clauses) + ')', tuple(params)


create_display_sql_command = '''
    DECLARE @p_display_name NVARCHAR(MAX) = ?,
        @p_factory_talk_view_se_id INT = ?,
        @p_date_time NVARCHAR(MAX) = ?,
        @p_user NVARCHAR(MAX) = ?,
        @p_width NVARCHAR(MAX) = ?,
        @p_height NVARCHAR(MAX) = ?;


    IF NOT EXISTS
    (
        SELECT *
        FROM SubObjects
        WHERE name = @p_display_name and ParentObjectID = @p_factory_talk_view_se_id
    )
        BEGIN
            DECLARE @sub_objectId		int
            declare @id table			(ID int)


            INSERT INTO SubObjects ([ParentObjectID]
                ,[ParentObjectImport]
                ,[Name]
                ,[DisplayName]
                ,[Type]
                ,[ChangeDate]
                ,[ChangeUser]
                ,[MajorRev]
                ,[MinorRev]
                ,[Lock]
                ,[MarkForDeletion]
                ,[Description]
                ,[OverrideDesc])
            OUTPUT INSERTED.SubObjectID into @ID
            VALUES (@p_factory_talk_view_se_id,'',@p_display_name,'Displays','GraphicDisplays',@p_date_time,@p_user,0,0,NULL,NULL,'ACM Display',0)



            SET @sub_objectID	=(SELECT TOP 1 ID FROM @ID )


            INSERT INTO SubParameters ([SubObjectID]
                ,[Name]
                ,[DataType]
                ,[Value]
                ,[RefType]
                ,[RefImport]
                ,[ChangeDate]
                ,[ChangeUser]
                ,[MajorRev]
                ,[MinorRev]
                ,[ParameterHelp]
                ,[RefValue])
            VALUES (@sub_objectID ,'DisplayTitle','String','Test',1,'',@p_date_time,@p_user,0,0,'Title of HMI display page',''),
                    (@sub_objectID ,'DisplayLeft','Int','0',1,'',@p_date_time,@p_user,0,0,'Display X position in pixels',''),
                    (@sub_objectID ,'DisplayTop','Int','0',1,'',@p_date_time,@p_user,0,0,'Display Y position in pixels',''),
                    (@sub_objectID ,'DisplayWidth','Int',@p_width,1,'',@p_date_time,@p_user,0,0,'Display width in pixels',''),
                    (@sub_objectID ,'DisplayHeight','Int',@p_height,1,'',@p_date_time,@p_user,0,0,'Display height in pixels',''),
                    (@sub_objectID ,'DisplayBackColor','String','silver',1,'',@p_date_time,@p_user,0,0,'Display background color',''),
                    (@sub_objectID ,'DisplaySecurity','String','*',1,'',@p_date_time,@p_user,0,0,'Display security',''),
                    (@sub_objectID ,'UpdateRate','Real','1.0',1,'',@p_date_time,@p_user,0,0,'Display update rate',''),
                    (@sub_objectID ,'LeftIndexMax','Int','7',1,'',@p_date_time,@p_user,0,0,'Index number of icons per row',''),
                    (@sub_objectID ,'VBAProjectObject','String','',1,'',@p_date_time,@p_user,0,0,'',''),
                    (@sub_objectID ,'SubObject Description','String','',1,'',@p_date_time,@p_user,0,0,'','');
        
    END;    
        '''
create_display_sql_command_params = ('display_name', 'factory_talk_view_se_id', 'date_time', 'user', 'width', 'height', )





create_line_sql_command = '''
    DECLARE @p_line_name NVARCHAR(MAX) = ?,
        @p_factory_talk_view_se_id INT = ?,
        @p_display_name NVARCHAR(MAX) = ?,
        @p_project_id INT = ?,
        @p_controller_id INT = ?,
        @p_parent_object_id INT = ?,
        @p_date_time NVARCHAR(MAX) = ?,
        @p_user NVARCHAR(MAX) = ?,
        @p_X1 NVARCHAR(MAX) = ?,
        @p_X2 NVARCHAR(MAX) = ?,
        @p_Y1 NVARCHAR(MAX) = ?,
        @p_Y2 NVARCHAR(MAX) = ?,
        @p_color NVARCHAR(MAX) = ?,
        @p_width NVARCHAR(MAX) = ?;


    IF NOT EXISTS
    (
        SELECT *
        FROM Objects
        WHERE name = @p_line_name and ParentObjectID = @p_factory_talk_view_se_id
    )
        BEGIN
            DECLARE @objectId		int
            declare @id table			(ID int)
            DECLARE @screenObjectId		int

            SET @screenObjectId = (SELECT TOP 1 SubObjectID FROM SubObjects where name = @p_display_name and ParentObjectID = @p_factory_talk_view_se_id)


            INSERT INTO Objects ([ProjectID]
                ,[ControllerID]
                ,[ParentObjectID]
                ,[ParentObjectImport]
                ,[Name]
                ,[CatalogNumber]
                ,[Description]
                ,[LibraryID]
                ,[LibraryType]
                ,[ChangeDate]
                ,[ChangeUser])
            OUTPUT INSERTED.ObjectID into @ID
            VALUES (@p_project_id,@p_controller_id,@p_parent_object_id,'',@p_line_name,'ProcessLine','Process Line','1E5825D5-62B1-4DF7-BA33-5BA0DDC2DCF3','DesignPattern',@p_date_time,@p_user)



            SET @objectId	=(SELECT TOP 1 ID FROM @ID )


            INSERT INTO Parameters ([ObjectID]
                ,[Name]
                ,[DataType]
                ,[Value]
                ,[RefType]
                ,[RefImport]
                ,[ChangeDate]
                ,[ChangeUser]
                ,[MajorRev]
                ,[MinorRev]
                ,[ParameterHelp]
                ,[RefValue])
            VALUES (@objectId ,'X1','Int',@p_X1,1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'X2','Int',@p_X2,1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'Y1','Int',@p_Y1,1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'Y2','Int',@p_Y2,1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'Color','String',@p_color,1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'Width','Int',@p_width,1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'SEAssocDisplay','String','',1,'',@p_date_time,@p_user,0,0,'Associated HMI SE Display',''),
                    (@objectId ,'MEAssocDisplay','String','',1,'',@p_date_time,@p_user,0,0,'Associated HMI ME Display','');
        

            UPDATE Parameters SET Value = @screenObjectId, RefType = 3 where ObjectID = @objectId and Name = 'SEAssocDisplay'
        
    END;
        '''
create_line_sql_command_params = ('line_name', 'factory_talk_view_se_id', 'display_name', 'project_id', 'controller_id', 'parent_object_id', 'date_time', 'user', 'X1', 'X2', 'Y1', 'Y2', 'color', 'width', )


create_image_sql_command = '''
    DECLARE @p_image_name NVARCHAR(MAX) = ?,
        @p_parent_object_id INT = ?,
        @p_display_name NVARCHAR(MAX) = ?,
        @p_factory_talk_view_se_id INT = ?,
        @p_project_id INT = ?,
        @p_controller_id INT = ?,
        @p_date_time NVARCHAR(MAX) = ?,
        @p_user NVARCHAR(MAX) = ?,
        @p_X1 NVARCHAR(MAX) = ?,
        @p_X2 NVARCHAR(MAX) = ?,
        @p_Y1 NVARCHAR(MAX) = ?,
        @p_Y2 NVARCHAR(MAX) = ?,
        @p_filename NVARCHAR(MAX) = ?,
        @p_image_id NVARCHAR(MAX) = ?;


    IF NOT EXISTS
    (
        SELECT *
        FROM Objects
        WHERE name = @p_image_name and ParentObjectID = @p_parent_object_id
    )
        BEGIN
            DECLARE @objectId		int
            declare @id table			(ID int)
            DECLARE @screenObjectId		int

            SET @screenObjectId = (SELECT TOP 1 [SubObjectID] FROM SubObjects where name = @p_display_name and ParentObjectID = @p_factory_talk_view_se_id)


            INSERT INTO Objects ([ProjectID]
                ,[ControllerID]
                ,[ParentObjectID]
                ,[ParentObjectImport]
                ,[Name]
                ,[CatalogNumber]
                ,[Description]
                ,[LibraryID]
                ,[LibraryType]
                ,[ChangeDate]
                ,[ChangeUser])
            OUTPUT INSERTED.ObjectID into @ID
            VALUES (@p_project_id,@p_controller_id,@p_parent_object_id,'',@p_image_name,'Image','HMI Image','F9366DE1-305F-4DCC-BB9E-58C28C019F23','DesignPattern',@p_date_time,@p_user)



            SET @objectId	=(SELECT TOP 1 ID FROM @ID )


            INSERT INTO Parameters ([ObjectID]
                ,[Name]
                ,[DataType]
                ,[Value]
                ,[RefType]
                ,[RefImport]
                ,[ChangeDate]
                ,[ChangeUser]
                ,[MajorRev]
                ,[MinorRev]
                ,[ParameterHelp]
                ,[RefValue])
            VALUES (@objectId ,'X1','Int',@p_X1,1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'X2','Int',@p_X2,1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'Y1','Int',@p_Y1,1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'Y2','Int',@p_Y2,1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'ImageName','String',@p_filename,1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'SolutionsProjectAcceleratorID','String',@p_image_id,1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'SEAssocDisplay','String','',1,'',@p_date_time,@p_user,0,0,'Associated HMI SE Display',''),
                    (@objectId ,'MEAssocDisplay','String','',1,'',@p_date_time,@p_user,0,0,'Associated HMI ME Display','');


            UPDATE Parameters SET Value = @screenObjectId, RefType = 3 where ObjectID = @objectId and Name = 'SEAssocDisplay'

    END;    
        
        '''
create_image_sql_command_params = ('image_name', 'parent_object_id', 'display_name', 'factory_talk_view_se_id', 'project_id', 'controller_id', 'date_time', 'user', 'X1', 'X2', 'Y1', 'Y2', 'filename', 'image_id', )

create_page_link_sql_command = '''
    DECLARE @p_page_link_name NVARCHAR(MAX) = ?,
        @p_parent_object_id INT = ?,
        @p_display_name NVARCHAR(MAX) = ?,
        @p_factory_talk_view_se_id INT = ?,
        @p_project_id INT = ?,
        @p_controller_id INT = ?,
        @p_date_time NVARCHAR(MAX) = ?,
        @p_user NVARCHAR(MAX) = ?,
        @p_center_x NVARCHAR(MAX) = ?,
        @p_center_y NVARCHAR(MAX) = ?,
        @p_navigate_to_display_name NVARCHAR(MAX) = ?,
        @p_label NVARCHAR(MAX) = ?,
        @p_orientation NVARCHAR(MAX) = ?,
        @p_page_link_id NVARCHAR(MAX) = ?;

    IF NOT EXISTS
    (
        SELECT *
        FROM Objects
        WHERE name = @p_page_link_name and ParentObjectID = @p_parent_object_id
    )
        BEGIN
            DECLARE @objectId		int
            declare @id table			(ID int)
            DECLARE @screenObjectId		int

            SET @screenObjectId = (SELECT TOP 1 [SubObjectID] FROM SubObjects where name = @p_display_name and ParentObjectID = @p_factory_talk_view_se_id)


            INSERT INTO Objects ([ProjectID]
                ,[ControllerID]
                ,[ParentObjectID]
                ,[ParentObjectImport]
                ,[Name]
                ,[CatalogNumber]
                ,[Description]
                ,[LibraryID]
                ,[LibraryType]
                ,[ChangeDate]
                ,[ChangeUser])
            OUTPUT INSERTED.ObjectID into @ID
            VALUES (@p_project_id,@p_controller_id,@p_parent_object_id,'',@p_page_link_name,'PageLink','HMI page link','C1A52D94-07A2-4309-80DC-ADB8BB971573','DesignPattern',@p_date_time,@p_user)



            SET @objectId	=(SELECT TOP 1 ID FROM @ID )


            INSERT INTO Parameters ([ObjectID]
                ,[Name]
                ,[DataType]
                ,[Value]
                ,[RefType]
                ,[RefImport]
                ,[ChangeDate]
                ,[ChangeUser]
                ,[MajorRev]
                ,[MinorRev]
                ,[ParameterHelp]
                ,[RefValue])
            VALUES (@objectId ,'CenterX','Int',@p_center_x,1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'CenterY','Int',@p_center_y,1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'NavToDisplayName','String',@p_navigate_to_display_name,1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'Label','String',@p_label,1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'SymbolOrientation','Int',@p_orientation,1,'',@p_date_time,@p_user,0,0,'Process Flow Direction. 0 = left to right (right), 1 = top to bottom (down), 2 = right to left (left), 3 = bottom to top (up)',''),
                    (@objectId ,'SymbolStyle','Int','0',1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'FriendlyName','String','',1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'SolutionsProjectAcceleratorID','String',@p_page_link_id,1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'SEAssocDisplay','String','',1,'',@p_date_time,@p_user,0,0,'Associated HMI SE Display',''),
                    (@objectId ,'MEAssocDisplay','String','',1,'',@p_date_time,@p_user,0,0,'Associated HMI ME Display','');


            UPDATE Parameters SET Value = @screenObjectId, RefType = 3 where ObjectID = @objectId and Name = 'SEAssocDisplay'
    
    END;     
        
        '''
create_page_link_sql_command_params = ('page_link_name', 'parent_object_id', 'display_name', 'factory_talk_view_se_id', 'project_id', 'controller_id', 'date_time', 'user', 'center_x', 'center_y', 'navigate_to_display_name', 'label', 'orientation', 'page_link_id', )


create_out_page_link_sql_command = '''
    DECLARE @p_page_link_name NVARCHAR(MAX) = ?,
        @p_display_name NVARCHAR(MAX) = ?,
        @p_factory_talk_view_se_id INT = ?,
        @p_project_id INT = ?,
        @p_controller_id INT = ?,
        @p_parent_object_id INT = ?,
        @p_date_time NVARCHAR(MAX) = ?,
        @p_user NVARCHAR(MAX) = ?,
        @p_center_x NVARCHAR(MAX) = ?,
        @p_center_y NVARCHAR(MAX) = ?,
        @p_navigate_to_display_name NVARCHAR(MAX) = ?,
        @p_label NVARCHAR(MAX) = ?;

    IF NOT EXISTS
    (
        SELECT *
        FROM Objects
        WHERE name = @p_page_link_name
    )
        BEGIN
            DECLARE @objectId		int
            declare @id table			(ID int)
            DECLARE @screenObjectId		int

            SET @screenObjectId = (SELECT TOP 1 [SubObjectID] FROM SubObjects where name = @p_display_name and ParentObjectID = @p_factory_talk_view_se_id)


            INSERT INTO Objects ([ProjectID]
                ,[ControllerID]
                ,[ParentObjectID]
                ,[ParentObjectImport]
                ,[Name]
                ,[CatalogNumber]
                ,[Description]
                ,[LibraryID]
                ,[LibraryType]
                ,[ChangeDate]
                ,[ChangeUser])
            OUTPUT INSERTED.ObjectID into @ID
            VALUES (@p_project_id,@p_controller_id,@p_parent_object_id,'',@p_page_link_name,'OutPageLink','HMI page link','BD742C50-7D83-4F28-B77F-4EC4BE912312','DesignPattern',@p_date_time,@p_user)



            SET @objectId	=(SELECT TOP 1 ID FROM @ID )


            INSERT INTO Parameters ([ObjectID]
                ,[Name]
                ,[DataType]
                ,[Value]
                ,[RefType]
                ,[RefImport]
                ,[ChangeDate]
                ,[ChangeUser]
                ,[MajorRev]
                ,[MinorRev]
                ,[ParameterHelp]
                ,[RefValue])
            VALUES (@objectId ,'CenterX','Int',@p_center_x,1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'CenterY','Int',@p_center_y,1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'NavToDisplayName','String',@p_navigate_to_display_name,1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'Label','String',@p_label,1,'',@p_date_time,@p_user,0,0,'',''),
                    (@objectId ,'SEAssocDisplay','String','',1,'',@p_date_time,@p_user,0,0,'Associated HMI SE Display',''),
                    (@objectId ,'MEAssocDisplay','String','',1,'',@p_date_time,@p_user,0,0,'Associated HMI ME Display','');


            UPDATE Parameters SET Value = @screenObjectId, RefType = 3 where ObjectID = @objectId and Name = 'SEAssocDisplay'
    
    END;     
        
        '''
create_out_page_link_sql_command_params = ('page_link_name', 'display_name', 'factory_talk_view_se_id', 'project_id', 'controller_id', 'parent_object_id', 'date_time', 'user', 'center_x', 'center_y', 'navigate_to_display_name', 'label', )


get_display_objects_sql_command = '''
    DECLARE @p_factory_talk_view_se_id INT = ?,
        @p_display_name NVARCHAR(MAX) = ?;

    SELECT 
        Objects.ObjectID,
        Objects.Name,
        Objects.CatalogNumber,
        Objects.Description,
        Objects.LibraryType,
        Objects.LibraryID,
        Objects.ControllerID,
        SubObjects.Name as DisplayName,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'Cfg_PositionX') as Cfg_PositionX,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'Cfg_PositionY') as Cfg_PositionY,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'isPositioned') as isPositioned,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'CenterX') as CenterX,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'CenterY') as CenterY,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'SolutionsProjectAcceleratorID') as SolutionsProjectAcceleratorID,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'X1') as X1,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'Y1') as Y1,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'X2') as X2,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'Y2') as Y2
    FROM 
        Objects
    INNER JOIN 
        Parameters ON Objects.ObjectID = Parameters.ObjectID
    INNER JOIN 
        SubObjects ON Parameters.Value = CAST(SubObjects.SubObjectID AS VARCHAR)
    WHERE 
        Parameters.RefType = 3
        AND SubObjects.ParentObjectID = @p_factory_talk_view_se_id
        AND SubObjects.Name = @p_display_name
    ORDER BY 
        Objects.Name
'''
get_display_objects_sql_command_params = ('factory_talk_view_se_id', 'display_name', )


get_display_object_sql_command = '''
    DECLARE @p_object_id INT = ?;

    SELECT 
        Objects.ObjectID,
        Objects.Name,
        Objects.CatalogNumber,
        Objects.Description,
        Objects.LibraryType,
        Objects.LibraryID,
        Objects.ControllerID,
        SubObjects.Name as DisplayName,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'Cfg_PositionX') as Cfg_PositionX,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'Cfg_PositionY') as Cfg_PositionY,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'isPositioned') as isPositioned,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'CenterX') as CenterX,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'CenterY') as CenterY,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'SolutionsProjectAcceleratorID') as SolutionsProjectAcceleratorID,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'X1') as X1,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'Y1') as Y1,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'X2') as X2,
        (SELECT Value FROM Parameters WHERE ObjectID = Objects.ObjectID AND Name = 'Y2') as Y2
    FROM 
        Objects
    INNER JOIN 
        Parameters ON Objects.ObjectID = Parameters.ObjectID
    INNER JOIN 
        SubObjects ON Parameters.Value = CAST(SubObjects.SubObjectID AS VARCHAR)
    WHERE 
        Parameters.RefType = 3
        AND Objects.ObjectID = @p_object_id
    ORDER BY 
        Objects.Name
'''
get_display_object_sql_command_params = ('object_id', )


get_displays_sql_command = '''
    DECLARE @p_factory_talk_view_se_id INT = ?;

    SELECT 
        SubObjects.SubObjectID,
        SubObjects.Name as DisplayName,
        SubObjects.DisplayName as DisplayType,
        SubObjects.Type,
        SubObjects.Description,
        SubObjects.ChangeDate,
        SubObjects.ChangeUser,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayWidth') as DisplayWidth,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayHeight') as DisplayHeight,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayTitle') as DisplayTitle,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayLeft') as DisplayLeft,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayTop') as DisplayTop,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplaySecurity') as DisplaySecurity,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayBackColor') as DisplayBackColor
    FROM 
        SubObjects
    WHERE 
        SubObjects.ParentObjectID = @p_factory_talk_view_se_id
    ORDER BY 
        SubObjects.Name
'''
get_displays_sql_command_params = ('factory_talk_view_se_id', )


get_display_sql_command = '''
    DECLARE @p_factory_talk_view_se_id INT = ?,
        @p_display_name NVARCHAR(MAX) = ?;

    SELECT 
        SubObjects.SubObjectID,
        SubObjects.Name as DisplayName,
        SubObjects.DisplayName as DisplayType,
        SubObjects.Type,
        SubObjects.Description,
        SubObjects.ChangeDate,
        SubObjects.ChangeUser,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayWidth') as DisplayWidth,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayHeight') as DisplayHeight,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayTitle') as DisplayTitle,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayLeft') as DisplayLeft,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayTop') as DisplayTop,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplaySecurity') as DisplaySecurity,
        (SELECT Value FROM SubParameters 
         WHERE SubObjectID = SubObjects.SubObjectID 
         AND Name = 'DisplayBackColor') as DisplayBackColor
    FROM 
        SubObjects
    WHERE 
        SubObjects.ParentObjectID = @p_factory_talk_view_se_id and SubObjects.Name = @p_display_name
    ORDER BY 
        SubObjects.Name
'''
get_display_sql_command_params = ('factory_talk_view_se_id', 'display_name', )


position_control_module_sql_command = '''
    DECLARE @p_display_name NVARCHAR(MAX) = ?,
        @p_factory_talk_view_se_id INT = ?,
        @p_date_time NVARCHAR(MAX) = ?,
        @p_user NVARCHAR(MAX) = ?,
        @p_control_module_id INT = ?,
        @p_position_x NVARCHAR(MAX) = ?,
        @p_position_y NVARCHAR(MAX) = ?,
        @p_orientation NVARCHAR(MAX) = ?;

            DECLARE @screenObjectId		int

            SET @screenObjectId = (SELECT TOP 1 [SubObjectID] FROM SubObjects where name = @p_display_name and ParentObjectID = @p_factory_talk_view_se_id)

            UPDATE Parameters SET Value = @screenObjectId, RefType = 3, ChangeDate = @p_date_time, ChangeUser = @p_user  where ObjectID = @p_control_module_id and Name = 'AssocDisplay'
            UPDATE Parameters SET Value = @p_position_x, ChangeDate = @p_date_time, ChangeUser = @p_user where ObjectID = @p_control_module_id and Name = 'Cfg_PositionX'
            UPDATE Parameters SET Value = @p_position_y, ChangeDate = @p_date_time, ChangeUser = @p_user where ObjectID = @p_control_module_id and Name = 'Cfg_PositionY'
            UPDATE Parameters SET Value = @p_orientation, ChangeDate = @p_date_time, ChangeUser = @p_user where ObjectID = @p_control_module_id and Name = 'SymbolOrientation'
            UPDATE Parameters SET Value = 1, ChangeDate = @p_date_time, ChangeUser = @p_user where ObjectID = @p_control_module_id and Name = 'isPositioned'  
        '''
position_control_module_sql_command_params = ('display_name', 'factory_talk_view_se_id', 'date_time', 'user', 'control_module_id', 'position_x', 'position_y', 'orientation', )      


write_parameter_value_sql_command = '''
    DECLARE @p_value NVARCHAR(MAX) = ?,
        @p_object_id INT = ?,
        @p_parameter NVARCHAR(MAX) = ?;

    UPDATE Parameters
    SET Value = @p_value

    WHERE ObjectID = @p_object_id and Name = @p_parameter
'''
write_parameter_value_sql_command_params = ('value', 'object_id', 'parameter', )


write_parameter_value_and_reftype_sql_command = '''
    DECLARE @p_value NVARCHAR(MAX) = ?,
        @p_ref_type INT = ?,
        @p_ref_value NVARCHAR(MAX) = ?,
        @p_object_id INT = ?,
        @p_parameter NVARCHAR(MAX) = ?;

    UPDATE Parameters
    SET Value = @p_value, RefType = @p_ref_type, RefValue = @p_ref_value
    
    WHERE ObjectID = @p_object_id and Name = @p_parameter
'''
write_parameter_value_and_reftype_sql_command_params = ('value', 'ref_type', 'ref_value', 'object_id', 'parameter', )


get_all_parameters_of_object = '''
    DECLARE @p_object_name NVARCHAR(MAX) = ?;

            SELECT * FROM Parameters where ObjectID = (select ObjectID from Objects where Name =@p_object_name) ORDER BY ObjectID ASC
            '''
get_all_parameters_of_object_params = ('object_name', )

get_all_subobjects_of_object = '''
    DECLARE @p_object_name NVARCHAR(MAX) = ?;

            SELECT * FROM SubObjects where ParentObjectID = (select ObjectID from Objects where Name =@p_object_name) ORDER BY SubObjectID
            '''
get_all_subobjects_of_object_params = ('object_name', )

get_all_subobjects_of_object = '''
    DECLARE @p_object_name NVARCHAR(MAX) = ?,
        @p_subobject_name_with_index NVARCHAR(MAX) = ?;
SELECT * FROM SubParameters where SubObjectID IN
            (SELECT SubObjectID FROM SubObjects where ParentObjectID = (select ObjectID from Objects where Name =@p_object_name))
            and SubObjectID = (SELECT SubObjectID FROM SubObjects where Name =@p_subobject_name_with_index AND ParentObjectID =(select ObjectID from Objects where Name =@p_object_name) )
            '''
get_all_subobjects_of_object_params = ('object_name', 'subobject_name_with_index', )

get_object = '''
    DECLARE @p_object_name NVARCHAR(MAX) = ?;

            SELECT * FROM Objects where Name =@p_object_name
            '''
get_object_params = ('object_name', )

get_all_objects = '''
    DECLARE @p_project_id INT = ?;

            SELECT Objects.ObjectID, Objects.Name FROM Objects
            inner join RegisteredLibraries on Objects.LibraryID = RegisteredLibraries.LibraryID 
            where Objects.ProjectID = @p_project_id
            '''
get_all_objects_params = ('project_id', )

get_all_objects_with_acm_filter = '''
    DECLARE @p_project_id INT = ?;

            SELECT Objects.ObjectID, Objects.Name FROM Objects
            inner join RegisteredLibraries on Objects.LibraryID = RegisteredLibraries.LibraryID 
            where Objects.ProjectID = @p_project_id
            {filter}
            '''
get_all_objects_with_acm_filter_params = ('project_id', )

get_all_subobjects_with_acm_filter = '''
    DECLARE @p_project_id INT = ?;

            SELECT SubObjects.SubObjectID
                , SubObjects.ParentObjectID
                , SubObjects.Name
                , SubObjects.DisplayName
                , Objects.ObjectID
                , Objects.Name as ObjectName  FROM SubObjects
            inner join Objects on SubObjects.ParentObjectID = Objects.ObjectID 
            inner join RegisteredLibraries on Objects.LibraryID = RegisteredLibraries.LibraryID 
            where Objects.ProjectID = @p_project_id
            {filter}
            '''
get_all_subobjects_with_acm_filter_params = ('project_id', )

create_subobject = '''
    DECLARE @p_subobject_name NVARCHAR(MAX) = ?,
        @p_parent_object_id INT = ?,
        @p_subobject_display_name NVARCHAR(MAX) = ?,
        @p_subobject_type NVARCHAR(MAX) = ?,
        @p_date_time NVARCHAR(MAX) = ?,
        @p_user NVARCHAR(MAX) = ?,
        @p_subobject_description NVARCHAR(MAX) = ?,
        @p_description_override INT = ?;


            IF NOT EXISTS
                (
                    SELECT *
                    FROM SubObjects
                    WHERE name = @p_subobject_name and ParentObjectID = @p_parent_object_id
                )

                BEGIN
                        DECLARE @sub_objectId		int
                        declare @id table			(ID int)


                        INSERT INTO SubObjects ([ParentObjectID]
                            ,[ParentObjectImport]
                            ,[Name]
                            ,[DisplayName]
                            ,[Type]
                            ,[ChangeDate]
                            ,[ChangeUser]
                            ,[MajorRev]
                            ,[MinorRev]
                            ,[Lock]
                            ,[MarkForDeletion]
                            ,[Description]
                            ,[OverrideDesc])
                        OUTPUT INSERTED.SubObjectID into @ID
                        VALUES (@p_parent_object_id,'',@p_subobject_name,@p_subobject_display_name,@p_subobject_type,@p_date_time,@p_user,NULL,NULL,NULL,NULL,@p_subobject_description,@p_description_override)


                        SET @sub_objectID	=(SELECT TOP 1 ID FROM @ID )

                        INSERT INTO SubParameters ([SubObjectID]
                            ,[Name]
                            ,[DataType]
                            ,[Value]
                            ,[RefType]
                            ,[RefImport]
                            ,[ChangeDate]
                            ,[ChangeUser]
                            ,[MajorRev]
                            ,[MinorRev]
                            ,[ParameterHelp]
                            ,[RefValue])

                        VALUES {subparameter_values};

                END;
            '''
create_subobject_params = ('subobject_name', 'parent_object_id', 'subobject_display_name', 'subobject_type', 'date_time', 'user', 'subobject_description', 'description_override', )

delete_subobject_sql_command = '''
    DECLARE @p_subobject_id INT = ?;

    IF EXISTS
    (
        SELECT *
        FROM SubObjects
        WHERE SubObjectID = @p_subobject_id
    )
    BEGIN
        DELETE FROM SubParameters WHERE SubObjectID = @p_subobject_id
        DELETE FROM SubObjects WHERE SubObjectID = @p_subobject_id
    END;
'''
delete_subobject_sql_command_params = ('subobject_id', )


subobject_subparameter_value_template = ' (@sub_objectID, ?, ?, ?, ?, \'\', ?, ?, NULL, NULL, ?, ?)'
subobject_subparameter_value_template_params = ('name', 'data_type', 'value', 'ref_type', 'change_date', 'user', 'parameter_help', 'ref_value', )


write_subparameter_value_sql_command = '''
    DECLARE @p_value NVARCHAR(MAX) = ?,
        @p_subobject_id INT = ?,
        @p_subparameter NVARCHAR(MAX) = ?;

    UPDATE SubParameters
    SET Value = @p_value 

    WHERE SubObjectID = @p_subobject_id and Name = @p_subparameter
'''
write_subparameter_value_sql_command_params = ('value', 'subobject_id', 'subparameter', )

write_subparameter_value_and_reftype_sql_command = '''
    DECLARE @p_value NVARCHAR(MAX) = ?,
        @p_ref_type INT = ?,
        @p_ref_value NVARCHAR(MAX) = ?,
        @p_subobject_id INT = ?,
        @p_subparameter NVARCHAR(MAX) = ?;

    UPDATE SubParameters
    SET Value = @p_value, RefType = @p_ref_type, RefValue = @p_ref_value

    WHERE SubObjectID = @p_subobject_id and Name = @p_subparameter
'''
write_subparameter_value_and_reftype_sql_command_params = ('value', 'ref_type', 'ref_value', 'subobject_id', 'subparameter', )
