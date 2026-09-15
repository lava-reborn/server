class lol.server.mess.CSM_M_getml extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_M_getml(id)
   {
      super();
      this._name = "getml";
      this.addProp("id",id);
   }
}
