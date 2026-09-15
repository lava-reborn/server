class lol.server.mess.CSM_SSGetStatInfo extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_SSGetStatInfo(type)
   {
      super();
      this._name = "ss_get_si";
      this.addProp("type",type);
   }
}
