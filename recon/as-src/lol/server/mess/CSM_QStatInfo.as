class lol.server.mess.CSM_QStatInfo extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_QStatInfo(q_type)
   {
      super();
      this._name = "q_si";
      this.addProp("q_type",q_type);
   }
}
