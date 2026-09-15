class lol.server.mess.CSM_SSGetSetInfo extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_SSGetSetInfo(type)
   {
      super();
      this._name = "ss_get_s_si";
      this.addProp("type",type);
   }
}
